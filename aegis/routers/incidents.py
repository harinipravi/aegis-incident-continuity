"""
Incidents and RCA endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from aegis.models.schemas import RCAResponse
from aegis.services.rca import RCACoordinatorService
from aegis.services.bigquery import BigQueryEvidenceService
from aegis.database import record_decision, get_latest_decision

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


@router.get("/{incident_id}/mitigation")
async def get_mitigation_decision(incident_id: str):
    decision = get_latest_decision(incident_id)

    if decision is None:
        return {
            "incident_id": incident_id,
            "decision": None
        }

    return decision
