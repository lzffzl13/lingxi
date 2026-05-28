import redis.asyncio as redis
from app.config import settings

_redis: redis.Redis | None = None


def get_redis() -> redis.Redis:
    """Get or create Redis connection."""
    global _redis
    if _redis is None:
        _redis = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            max_connections=20,
        )
    return _redis


async def close_redis(r: redis.Redis | None = None) -> None:
    """Close Redis connection."""
    global _redis
    target = r or _redis
    if target is not None:
        await target.close()
        if r is None:
            _redis = None
