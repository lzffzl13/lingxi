"""Health check endpoint with database status."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import AgentDep, RedisDep
from app.config import settings
from app.db.database import async_session_factory
from app.cache import get_response_cache

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


@router.get("/health", response_model=HealthResponse)
async def health(r: RedisDep, agent: AgentDep):
    """Health check endpoint.

    Returns service status and component health.
    Used by Docker HEALTHCHECK and load balancers.
    """
    redis_ok = False
    llm_ok = False
    db_ok = False

    # Check Redis
    try:
        await r.ping()
        redis_ok = True
    except Exception:
        pass

    # Check LLM
    try:
        llm_ok = await agent.llm.health_check()
    except Exception:
        pass

    # Check Database (optional)
    try:
        if async_session_factory:
            async with async_session_factory() as session:
                await session.execute("SELECT 1")
                db_ok = True
    except Exception:
        pass

    # Determine overall status
    if redis_ok and llm_ok:
        status = "ok"
    elif redis_ok or llm_ok:
        status = "degraded"
    else:
        status = "unhealthy"

    return HealthResponse(
        status=status,
        version=settings.VERSION,
        redis="connected" if redis_ok else "disconnected",
        llm="available" if llm_ok else "unavailable",
        database="connected" if db_ok else "not_configured",
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
