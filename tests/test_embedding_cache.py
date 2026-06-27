"""Embedding cache tests."""

from unittest.mock import AsyncMock

import pytest

from app.cache.embedding_cache import EmbeddingCache
from app.rag.embeddings import CachedEmbeddingProvider


@pytest.mark.asyncio
async def test_embedding_cache_normalizes_whitespace():
    redis_client = AsyncMock()
    cache = EmbeddingCache(redis_client=redis_client, ttl_seconds=60)
    redis_client.get.return_value = '{"embedding": [1.0, 2.0]}'

    result = await cache.get("test-model", "hello   \n  world")

    assert result == [1.0, 2.0]
    redis_client.get.assert_awaited_once()


@pytest.mark.asyncio
async def test_cached_embedding_provider_reads_cache_before_calling_provider():
    provider = AsyncMock()
    provider.model = "test-model"
    provider.dimension = 2
    provider.return_value = [[0.5, 0.5]]

    cache = AsyncMock()
    cache.get.side_effect = [[1.0, 0.0], None]

    wrapped = CachedEmbeddingProvider(provider=provider, cache=cache)

    result = await wrapped(["cached", "fresh"])

    assert result == [[1.0, 0.0], [0.5, 0.5]]
    provider.assert_awaited_once_with(["fresh"])
    cache.set.assert_awaited_once_with("test-model", "fresh", [0.5, 0.5], 2)
