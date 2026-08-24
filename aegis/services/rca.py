"""
RCA coordination service that integrates BigQuery extraction and Gemini reasoning.
"""

from typing import Dict, Any, List
from aegis.services.bigquery import BigQueryEvidenceService
from aegis.services.gemini import GeminiReasoningService


class RCACoordinatorService:
    def __init__(self):
        self.bq_service = BigQueryEvidenceService()
        self.gemini_service = GeminiReasoningService()

    async def conduct_rca(self, incident_id: str) -> Dict[str, Any]:
        """
        Coordinates full RCA flow:
        1. Extract evidence from BigQuery using incident_id.
        2. Execute Gemini reasoning model on the evidence packet.
        3. Merge authoritative incident fields from BigQuery with Gemini output.
        4. Synthesize metrics/logs/deployment analysis from evidence.
        """
        evidence = await self.bq_service.get_incident_evidence(incident_id)

        rca_result = await self.gemini_service.analyze_evidence(evidence)

        # Merge authoritative fields from BigQuery evidence into the RCA result.
        # incident_id and service_name must come from the evidence, not Gemini.
        rca_result["incident_id"] = evidence["incident_id"]
        rca_result["service_name"] = evidence["incident"]["service_name"]

        # Synthesize structured analysis sections from the retrieved evidence.
        rca_result["metrics_analysis"] = self._build_metrics_analysis(
            evidence.get("service_metrics", []),
            evidence["incident"]["service_name"],
        )
        rca_result["logs_analysis"] = self._build_logs_analysis(
            evidence.get("application_logs", [])
        )
        rca_result["deployment_analysis"] = self._build_deployment_analysis(
            evidence.get("deployments", [])
        )

        return rca_result

    # ------------------------------------------------------------------
    # Evidence synthesis helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_metrics_analysis(
        metrics: List[Dict[str, Any]], target_service: str
    ) -> Dict[str, Any]:
        """
        Derive anomalies_detected and correlation_notes from raw metrics.
        Flags data points with high error_rate, high latency, or low db_connections.
        """
        anomalies: List[str] = []
        target_metrics = [m for m in metrics if m.get("service_name") == target_service]

        for m in target_metrics:
            ts = m.get("timestamp", "?")
            error_rate = m.get("error_rate", 0)
            latency = m.get("latency_ms", 0)
            db_conn = m.get("db_connections")

            parts = []
            if error_rate and error_rate > 0.3:
                parts.append(f"error_rate={error_rate}")
            if latency and latency > 2000:
                parts.append(f"latency_ms={latency}")
            if db_conn is not None and db_conn <= 5:
                parts.append(f"db_connections={db_conn}")

            if parts:
                anomalies.append(f"[{ts}] {target_service}: {', '.join(parts)}")

        # Build a correlation note summarising the overall picture
        if anomalies:
            correlation = (
                f"Found {len(anomalies)} anomalous metric intervals for "
                f"{target_service} out of {len(target_metrics)} total data points "
                f"in the incident window."
            )
        else:
            correlation = f"No significant metric anomalies detected for {target_service}."

        return {
            "anomalies_detected": anomalies,
            "correlation_notes": correlation,
        }

    @staticmethod
    def _build_logs_analysis(logs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Derive error_patterns and suspect_traces from retrieved application logs.
        Groups by error_code and collects unique trace IDs.
        """
        error_code_counts: Dict[str, int] = {}
        suspect_traces: List[str] = []
        seen_traces = set()

        for log in logs:
            code = log.get("error_code", "UNKNOWN")
            msg = log.get("message", "")
            trace = log.get("trace_id", "")

            error_code_counts[code] = error_code_counts.get(code, 0) + 1

            if trace and trace not in seen_traces:
                seen_traces.add(trace)
                suspect_traces.append(trace)

        error_patterns = [
            f"{code} (×{count})" for code, count in
            sorted(error_code_counts.items(), key=lambda x: x[1], reverse=True)
        ]

        return {
            "error_patterns": error_patterns,
            "suspect_traces": suspect_traces[:20],  # Cap to avoid excessively large responses
        }

    @staticmethod
    def _build_deployment_analysis(
        deployments: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Derive suspect_deployments and configuration_changes from retrieved deployments.
        Uses exact values present in the evidence.
        """
        suspect_deployments: List[str] = []
        configuration_changes: List[str] = []

        for dep in deployments:
            deploy_id = dep.get("deployment_id", "unknown")
            service = dep.get("service_name", "unknown")
            version = dep.get("version", "unknown")
            deploy_time = dep.get("deployment_time", "?")
            change_type = dep.get("change_type", "unknown")
            changed = dep.get("changed_components", "")

            suspect_deployments.append(
                f"{deploy_id}: {service} {version} at {deploy_time} ({change_type})"
            )
            if changed:
                configuration_changes.append(
                    f"{deploy_id}: {changed}"
                )

        return {
            "suspect_deployments": suspect_deployments,
            "configuration_changes": configuration_changes,
        }


