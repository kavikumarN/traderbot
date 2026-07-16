"""Liveness/readiness probes.

Deliberately unversioned and outside ``/api/v1`` — these are infrastructure
endpoints consumed by the orchestrator (Kubernetes, Docker Compose
healthcheck), not the product API, and their contract must stay stable
across API versions.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.logging import get_logger
from app.interface.api.deps import get_redis, get_session_factory, get_settings_dep

router = APIRouter(tags=["health"])
logger = get_logger(__name__)


@router.get("/health/live", summary="Liveness probe")
async def live() -> dict[str, str]:
    """No dependency checks — only answers 'is the process able to serve requests at all'."""
    return {"status": "ok"}


@router.get("/health/ready", summary="Readiness probe")
async def ready(
    response: Response,
    settings: Settings = Depends(get_settings_dep),
    session_factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
    redis: Redis = Depends(get_redis),
) -> dict[str, object]:
    checks: dict[str, str] = {}

    try:
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        logger.exception("Readiness check failed: database")
        checks["database"] = "unavailable"

    try:
        await redis.ping()
        checks["redis"] = "ok"
    except Exception:
        logger.exception("Readiness check failed: redis")
        checks["redis"] = "unavailable"

    all_ok = all(value == "ok" for value in checks.values())
    response.status_code = status.HTTP_200_OK if all_ok else status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ok" if all_ok else "degraded", "checks": checks, "version": settings.app_name}
