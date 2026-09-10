"""
Incidents and RCA endpoints.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from aegis.models.schemas import RCAResponse
from aegis.services.rca import RCACoordinatorService
from aegis.services.bigquery import BigQueryEvidenceService
from aegis.database import (
    record_decision,
    get_latest_decision,
    save_rca_result,
    list_rca_results,
    set_incident_status,
    get_incident_status,
    save_runbook,
    list_runbooks,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/incidents", tags=["Incidents"])


class MitigationDecision(BaseModel):
    decision: str


@router.get("")
async def list_incidents(
    limit: int = 50,
    bq_service: BigQueryEvidenceService = Depends()
):
    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=400,
            detail="Limit must be between 1 and 100"
        )

    try:
        return await bq_service.list_incidents(limit)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# NOTE: This route MUST be declared before /{incident_id} so that FastAPI
# does not treat the literal string "rca-history" as an incident ID.
@router.get("/rca-history")
async def list_rca_history(limit: int = 20):
    """Return the most recent RCA results stored in the local SQLite database."""
    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=400,
            detail="Limit must be between 1 and 100"
        )
    return list_rca_results(limit)


@router.get("/{incident_id}/status")
async def get_status(incident_id: str):
    return get_incident_status(incident_id)


@router.post("/{incident_id}/resolve")
async def resolve_incident(incident_id: str):
    decision = get_latest_decision(incident_id)

    if decision is None or decision.get("decision") != "APPROVED":
        raise HTTPException(
            status_code=400,
            detail="Incident can only be resolved after mitigation is approved"
        )

    resolved_at = datetime.now(timezone.utc).isoformat()

    return set_incident_status(
        incident_id,
        "RESOLVED",
        resolved_at,
    )


@router.get("/runbooks")
async def get_runbooks(limit: int = 50):
    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=400,
            detail="Limit must be between 1 and 100"
        )

    return list_runbooks(limit)


@router.get("/{incident_id}")
async def get_incident(
    incident_id: str,
    bq_service: BigQueryEvidenceService = Depends()
):
    try:
        return await bq_service.extract_incident(incident_id)

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{incident_id}/rca", response_model=RCAResponse)
async def trigger_rca(
    incident_id: str,
    rca_service: RCACoordinatorService = Depends()
):
    try:
        result = await rca_service.conduct_rca(incident_id=incident_id)

        # Persist RCA result for history; non-fatal if persistence fails.
        try:
            save_rca_result(incident_id, result)
        except Exception as persist_err:
            logger.warning(
                "Failed to persist RCA result for %s: %s", incident_id, persist_err
            )

        return result

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{incident_id}/mitigation")
async def save_mitigation_decision(
    incident_id: str,
    payload: MitigationDecision
):
    decision = payload.decision.upper()

    if decision not in {"APPROVED", "REJECTED"}:
        raise HTTPException(
            status_code=400,
            detail="Decision must be APPROVED or REJECTED"
        )

    return record_decision(incident_id, decision)


@router.post("/{incident_id}/runbook")
async def create_runbook(incident_id: str):
    decision = get_latest_decision(incident_id)

    if decision is None or decision.get("decision") != "APPROVED":
        raise HTTPException(
            status_code=400,
            detail="Runbook can only be created after mitigation is approved"
        )

    from aegis.database import get_connection
    import json

    conn = get_connection()

    try:
        row = conn.execute(
            """
            SELECT result_json
            FROM rca_results
            WHERE incident_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (incident_id,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        raise HTTPException(
            status_code=400,
            detail="Generate an RCA before creating a runbook"
        )

    result = json.loads(row["result_json"])

    return save_runbook(
        incident_id=incident_id,
        service_name=result.get("service_name", ""),
        title=f"{result.get('service_name', incident_id)} Incident Recovery Runbook",
        root_cause=result.get("suspected_root_cause", ""),
        mitigation=result.get("recommended_mitigation", ""),
        evidence_summary=result.get("evidence_summary", ""),
    )


@router.get("/{incident_id}/mitigation")
async def get_mitigation_decision(incident_id: str):
    decision = get_latest_decision(incident_id)

    if decision is None:
        return {
            "incident_id": incident_id,
            "decision": None
        }

    return decision
