"""Embedding cache backed by Redis."""

import hashlib
import json
import re
from typing import Optional

import redis.asyncio as redis

from app.monitoring import track_cache_hit, track_cache_miss
from app.utils.logger import logger


class EmbeddingCache:
    """Cache embedding vectors by model and normalized text."""

    def __init__(self, redis_client: redis.Redis, ttl_seconds: int = 2592000):
        self.redis = redis_client
        self.ttl_seconds = ttl_seconds

    def _normalize_text(self, text: str) -> str:
        stripped = text.strip()
        return re.sub(r"\s+", " ", stripped)

    def _cache_key(self, model: str, text: str) -> str:
        normalized = self._normalize_text(text)
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        return f"embedding:{model}:{digest}"

    async def get(self, model: str, text: str) -> Optional[list[float]]:
        key = self._cache_key(model, text)

        try:
            cached = await self.redis.get(key)
        except Exception as exc:
            logger.warning(f"Embedding cache read failed: {exc}")
            return None

        if cached is None:
            track_cache_miss("embedding")
            return None

        try:
            payload = json.loads(cached)
            embedding = payload.get("embedding")
            if not isinstance(embedding, list):
                track_cache_miss("embedding")
                return None
            track_cache_hit("embedding")
            return embedding
        except (TypeError, json.JSONDecodeError) as exc:
            logger.warning(f"Embedding cache decode failed: {exc}")
            track_cache_miss("embedding")
            return None

    async def set(self, model: str, text: str, embedding: list[float], dimension: int) -> None:
        key = self._cache_key(model, text)
        payload = {
            "model": model,
            "dimension": dimension,
            "embedding": embedding,
        }

        try:
            await self.redis.set(key, json.dumps(payload), ex=self.ttl_seconds)
        except Exception as exc:
            logger.warning(f"Embedding cache write failed: {exc}")
