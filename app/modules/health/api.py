from fastapi import APIRouter, Response, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.db import SessionDep
from app.modules.health.schemas import HealthResponse, ReadinessResponse
from app.settings import get_settings

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def liveness() -> HealthResponse:
    """The process is up. Used by the container orchestrator to restart a dead app."""
    return HealthResponse(status="ok", version=get_settings().VERSION)


@router.get("/ready")
async def readiness(session: SessionDep, response: Response) -> ReadinessResponse:
    """The app can serve traffic: its database answers."""
    try:
        await session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessResponse(status="unavailable", database="unavailable")
    return ReadinessResponse(status="ok", database="ok")
