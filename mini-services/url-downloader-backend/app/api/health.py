"""
Health check endpoint.
"""

from fastapi import APIRouter
from app.schemas.download import HealthResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Check if the service is healthy.",
)
async def health_check() -> dict:
    """Return service health status."""
    return {"status": "healthy"}
