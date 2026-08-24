from fastapi import APIRouter
from aegis.models.schemas import HealthResponse

router = APIRouter()

@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check endpoint",
    description="Returns the current operational status of the service."
)
async def health_check() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="aegis-incident-continuity"
    )
