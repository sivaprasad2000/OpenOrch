from typing import Any

from fastapi import APIRouter

from app.core.config import settings
from app.models.common import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
    )


@router.get("/readiness", tags=["Health"])
async def readiness_check() -> dict[str, Any]:
    return {"status": "ready"}


@router.get("/liveness", tags=["Health"])
async def liveness_check() -> dict[str, Any]:
    return {"status": "alive"}
