"""Health check endpoint with database status."""

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.api.deps import AgentDep, RedisDep
from app.cache import get_response_cache
from app.config import settings
from app.db.database import async_session_factory

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    version: str
    redis: str
    llm: str
    database: str


class CacheStats(BaseModel):
    size: int
    max_size: int
    ttl_seconds: int
    expired_entries: int


def _derive_health_status(redis_ok: bool, llm_ok: bool, database_status: str) -> str:
    """Summarize component health into a single service status."""
    required_ok = redis_ok and llm_ok
    database_ok = database_status in {"connected", "not_configured"}

    if required_ok and database_ok:
        return "ok"

    if redis_ok or llm_ok or database_status == "connected":
        return "degraded"

    return "unhealthy"


@router.get("/health", response_model=HealthResponse)
async def health(r: RedisDep, agent: AgentDep):
    """Return service status and component health."""
    redis_ok = False
    llm_ok = False
    database_status = "not_configured"

    try:
        await r.ping()
        redis_ok = True
    except Exception:
        redis_ok = False

    try:
        llm_ok = await agent.llm.health_check()
    except Exception:
        llm_ok = False

    if settings.DATABASE_URL:
        database_status = "unavailable"
        if async_session_factory:
            try:
                async with async_session_factory() as session:
                    await session.execute(text("SELECT 1"))
                    database_status = "connected"
            except Exception:
                database_status = "unavailable"

    status = _derive_health_status(redis_ok, llm_ok, database_status)

    return HealthResponse(
        status=status,
        version=settings.VERSION,
        redis="connected" if redis_ok else "disconnected",
        llm="available" if llm_ok else "unavailable",
        database=database_status,
    )


@router.get("/cache/stats", response_model=CacheStats)
async def cache_stats():
    """Get response cache statistics."""
    cache = get_response_cache()
    stats = cache.stats()
    return CacheStats(**stats)


@router.post("/cache/clear")
async def clear_cache():
    """Clear response cache."""
    cache = get_response_cache()
    cache.clear()
    return {"message": "Cache cleared successfully"}
