"""
Incidents and RCA endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends
from aegis.models.schemas import RCAResponse
from aegis.services.rca import RCACoordinatorService

router = APIRouter(prefix="/incidents", tags=["Incidents"])

@router.post("/{incident_id}/rca", response_model=RCAResponse)
async def trigger_rca(
    incident_id: str,
    rca_service: RCACoordinatorService = Depends()
):
    """
    Trigger automated Root Cause Analysis (RCA) for a specific P1 incident.
    Only the incident_id is required; the evidence service resolves all
    other context (service, timing, dependencies) from BigQuery.
    """
    try:
        result = await rca_service.conduct_rca(incident_id=incident_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

