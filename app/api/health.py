from fastapi import APIRouter
from app.models.schemas import HealthResponse
from app.utils.logger import logger

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    redis_ok = False
    llm_ok = False

    try:
        from app.main import get_redis_client
        r = get_redis_client()
        await r.ping()
        redis_ok = True
    except Exception:
        pass

    try:
        from app.main import get_agent
        agent = get_agent()
        llm_ok = await agent.llm.health_check()
    except Exception:
        pass

    status = "ok" if (redis_ok and llm_ok) else "degraded"

    return HealthResponse(
        status=status,
        redis="connected" if redis_ok else "disconnected",
        llm="available" if llm_ok else "unavailable",
        version="0.1.0",
    )
