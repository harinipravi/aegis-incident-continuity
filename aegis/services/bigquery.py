"""
BigQuery integration service for extracting incident telemetry and evidence.

Queries the aegis_ops dataset tables:
  - incidents
  - service_dependencies
  - service_metrics
  - application_logs
  - deployments
"""

import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta, timezone
from google.cloud import bigquery
from google.cloud.exceptions import GoogleCloudError
from aegis.config import settings

logger = logging.getLogger(__name__)


def get_bigquery_client() -> bigquery.Client:
    """
    Returns a BigQuery Client initialized with the project setting.
    Uses Google Application Default Credentials (ADC) by default.
    """
    return bigquery.Client(project=settings.GOOGLE_CLOUD_PROJECT)


def _row_to_dict(row: bigquery.Row) -> Dict[str, Any]:
    """
    Convert a BigQuery Row to a plain dict with JSON-serializable values.
    Converts datetime objects to ISO 8601 strings.
    """
    result = {}
    for key, value in row.items():
        if isinstance(value, datetime):
            result[key] = value.isoformat()
        else:
            result[key] = value
    return result


def _run_query(
    client: bigquery.Client,
    sql: str,
    params: List[bigquery.ScalarQueryParameter] = None,
    description: str = "BigQuery query",
) -> List[Dict[str, Any]]:
    """
    Execute a parameterized BigQuery query and return results as a list of dicts.
    Raises RuntimeError with context on BigQuery failures.
    """
    job_config = bigquery.QueryJobConfig()
    if params:
        job_config.query_parameters = params

    try:
        query_job = client.query(sql, job_config=job_config)
        rows = query_job.result()
        return [_row_to_dict(row) for row in rows]
    except GoogleCloudError as e:
        logger.error("BigQuery error during %s: %s", description, e)
        raise RuntimeError(f"BigQuery query failed ({description}): {e}") from e


class BigQueryEvidenceService:
    """
    Extracts incident evidence from BigQuery tables in the aegis_ops dataset.
    """

    def __init__(self):
        self.client = get_bigquery_client()
        self.dataset = settings.BIGQUERY_DATASET
        self.project = settings.GOOGLE_CLOUD_PROJECT

    @property
    def _table(self) -> str:
        """Returns the fully-qualified dataset prefix: `project.dataset`."""
        return f"`{self.project}.{self.dataset}`"

    def _fqn(self, table_name: str) -> str:
        """Returns a fully-qualified table name."""
        return f"`{self.project}.{self.dataset}.{table_name}`"

    # ------------------------------------------------------------------
    # Individual evidence extraction methods
    # ------------------------------------------------------------------

    async def list_incidents(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Retrieve recent incidents from the incidents table.
        """
        sql = f"""
            SELECT
                incident_id,
                timestamp,
                severity,
                service_name,
                symptoms,
                resolution,
                duration_minutes
            FROM {self._fqn('incidents')}
            ORDER BY timestamp DESC
            LIMIT @result_limit
        """

        params = [
            bigquery.ScalarQueryParameter("result_limit", "INT64", limit),
        ]

        return _run_query(
            self.client,
            sql,
            params,
            description="list_incidents",
        )

    async def extract_incident(self, incident_id: str) -> Dict[str, Any]:
        """
        Retrieve the target incident record from the incidents table.
        Returns the incident details WITHOUT the actual_root_cause field,
        so that Gemini must infer the root cause from evidence alone.
        """
        sql = f"""
            SELECT
                incident_id,
                timestamp,
                severity,
                service_name,
                symptoms,
                resolution,
                duration_minutes
            FROM {self._fqn('incidents')}
            WHERE incident_id = @incident_id
            LIMIT 1
        """
        params = [
            bigquery.ScalarQueryParameter("incident_id", "STRING", incident_id),
        ]
        results = _run_query(
            self.client, sql, params,
            description=f"extract_incident({incident_id})"
        )
        if not results:
            raise ValueError(f"Incident {incident_id} not found in BigQuery")
        return results[0]

    async def extract_dependencies(
        self, service_name: str
    ) -> List[Dict[str, Any]]:
        """
        Query service_dependencies for upstream and downstream services
        connected to the target service (as source or target).
        """
        sql = f"""
            SELECT
                source_service,
                target_service,
                dependency_type
            FROM {self._fqn('service_dependencies')}
            WHERE source_service = @service_name
               OR target_service = @service_name
        """
        params = [
            bigquery.ScalarQueryParameter("service_name", "STRING", service_name),
        ]
        return _run_query(
            self.client, sql, params,
            description=f"extract_dependencies({service_name})"
        )

    async def extract_metrics(
        self,
        service_names: List[str],
        window_start: datetime,
        window_end: datetime,
    ) -> List[Dict[str, Any]]:
        """
        Query service_metrics for the given services within the time window.
        Orders by timestamp ascending.
        """
        sql = f"""
            SELECT
                timestamp,
                service_name,
                cpu_percent,
                memory_percent,
                request_count,
                error_rate,
                latency_ms,
                db_connections
            FROM {self._fqn('service_metrics')}
            WHERE service_name IN UNNEST(@service_names)
              AND timestamp BETWEEN @window_start AND @window_end
            ORDER BY timestamp ASC
        """
        params = [
            bigquery.ArrayQueryParameter("service_names", "STRING", service_names),
            bigquery.ScalarQueryParameter("window_start", "TIMESTAMP", window_start),
            bigquery.ScalarQueryParameter("window_end", "TIMESTAMP", window_end),
        ]
        return _run_query(
            self.client, sql, params,
            description=f"extract_metrics({service_names})"
        )

    async def extract_logs(
        self,
        service_names: List[str],
        window_start: datetime,
        window_end: datetime,
    ) -> List[Dict[str, Any]]:
        """
        Query application_logs for ERROR, CRITICAL, and FATAL severity
        entries for the given services within the time window.
        Orders by timestamp ascending.
        """
        sql = f"""
            SELECT
                timestamp,
                service_name,
                severity,
                error_code,
                message,
                trace_id
            FROM {self._fqn('application_logs')}
            WHERE service_name IN UNNEST(@service_names)
              AND severity IN ('ERROR', 'CRITICAL', 'FATAL')
              AND timestamp BETWEEN @window_start AND @window_end
            ORDER BY timestamp ASC
        """
        params = [
            bigquery.ArrayQueryParameter("service_names", "STRING", service_names),
            bigquery.ScalarQueryParameter("window_start", "TIMESTAMP", window_start),
            bigquery.ScalarQueryParameter("window_end", "TIMESTAMP", window_end),
        ]
        return _run_query(
            self.client, sql, params,
            description=f"extract_logs({service_names})"
        )

    async def extract_deployments(
        self,
        service_names: List[str],
        incident_start: datetime,
        lookback_hours: int = 24,
    ) -> List[Dict[str, Any]]:
        """
        Query deployments for the given services within a lookback window
        (default 24 hours) prior to the incident start time.
        Orders by deployment_time descending (most recent first).
        """
        lookback_start = incident_start - timedelta(hours=lookback_hours)
        sql = f"""
            SELECT
                deployment_id,
                service_name,
                version,
                deployment_time,
                change_type,
                changed_components
            FROM {self._fqn('deployments')}
            WHERE service_name IN UNNEST(@service_names)
              AND deployment_time BETWEEN @lookback_start AND @incident_start
            ORDER BY deployment_time DESC
        """
        params = [
            bigquery.ArrayQueryParameter("service_names", "STRING", service_names),
            bigquery.ScalarQueryParameter("lookback_start", "TIMESTAMP", lookback_start),
            bigquery.ScalarQueryParameter("incident_start", "TIMESTAMP", incident_start),
        ]
        return _run_query(
            self.client, sql, params,
            description=f"extract_deployments({service_names})"
        )

    async def extract_historical_incidents(
        self,
        service_name: str,
        before: datetime,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Query up to `limit` prior incidents for the same service,
        ordered by most recent first. Includes actual_root_cause and
        resolution to provide learning context for Gemini.
        """
        sql = f"""
            SELECT
                incident_id,
                timestamp,
                severity,
                service_name,
                symptoms,
                actual_root_cause,
                resolution,
                duration_minutes
            FROM {self._fqn('incidents')}
            WHERE service_name = @service_name
              AND timestamp < @before
            ORDER BY timestamp DESC
            LIMIT @result_limit
        """
        params = [
            bigquery.ScalarQueryParameter("service_name", "STRING", service_name),
            bigquery.ScalarQueryParameter("before", "TIMESTAMP", before),
            bigquery.ScalarQueryParameter("result_limit", "INT64", limit),
        ]
        return _run_query(
            self.client, sql, params,
            description=f"extract_historical_incidents({service_name})"
        )

    # ------------------------------------------------------------------
    # Evidence packet coordinator
    # ------------------------------------------------------------------

    async def get_incident_evidence(
        self, incident_id: str
    ) -> Dict[str, Any]:
        """
        Build a complete evidence packet for the given incident.

        Steps:
          1. Fetch the target incident to determine service and time window.
          2. Fetch service dependencies for the target service.
          3. Build the list of relevant services (target + dependencies).
          4. Fetch metrics, logs, and deployments for all relevant services.
          5. Fetch historical incidents for the target service.

        Returns a dict suitable for passing to the Gemini RCA service.
        """
        # 1. Target incident
        incident = await self.extract_incident(incident_id)
        service_name = incident["service_name"]
        incident_ts_str = incident["timestamp"]

        # Parse incident timestamp (ISO format from _row_to_dict)
        incident_start = datetime.fromisoformat(incident_ts_str)
        if incident_start.tzinfo is None:
            incident_start = incident_start.replace(tzinfo=timezone.utc)

        duration = incident.get("duration_minutes") or 120
        window_start = incident_start - timedelta(hours=1)
        window_end = incident_start + timedelta(minutes=duration, hours=1)

        # 2. Service dependencies
        dependencies = await self.extract_dependencies(service_name)

        # 3. Build list of all relevant services
        related_services = set()
        for dep in dependencies:
            related_services.add(dep["source_service"])
            related_services.add(dep["target_service"])
        related_services.add(service_name)
        all_services = sorted(related_services)

        # 4. Metrics, logs, deployments for relevant services
        metrics = await self.extract_metrics(all_services, window_start, window_end)
        logs = await self.extract_logs(all_services, window_start, window_end)
        deployments = await self.extract_deployments(all_services, incident_start)

        # 5. Historical incidents for context
        historical = await self.extract_historical_incidents(
            service_name, incident_start
        )

        evidence_packet = {
            "incident_id": incident_id,
            "incident": incident,
            "time_window": {
                "start": window_start.isoformat(),
                "end": window_end.isoformat(),
            },
            "service_dependencies": dependencies,
            "related_services": all_services,
            "service_metrics": metrics,
            "application_logs": logs,
            "deployments": deployments,
            "historical_incidents": historical,
            "summary": {
                "metrics_count": len(metrics),
                "logs_count": len(logs),
                "deployments_count": len(deployments),
                "dependencies_count": len(dependencies),
                "historical_incidents_count": len(historical),
            },
        }

        logger.info(
            "Evidence packet for %s: %d metrics, %d logs, %d deployments, "
            "%d dependencies, %d historical incidents",
            incident_id,
            len(metrics),
            len(logs),
            len(deployments),
            len(dependencies),
            len(historical),
        )

        return evidence_packet
