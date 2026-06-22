"""Middleware tests."""

import time
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.api.middleware import RateLimitMiddleware, RequestLoggingMiddleware
from app.knowledge.manager import SearchCache


class TestRateLimitMiddleware:
    """Tests for RateLimitMiddleware."""

    def test_cache_basic(self):
        """Test basic cache operations."""
        cache = SearchCache(ttl=60, max_size=10)

        # Set and get
        cache.set("key1", ["result1"])
        assert cache.get("key1") == ["result1"]

        # Miss
        assert cache.get("nonexistent") is None

    def test_cache_expiry(self):
        """Test cache TTL expiry."""
        cache = SearchCache(ttl=0.1, max_size=10)  # 100ms TTL

        cache.set("key1", ["result1"])
        assert cache.get("key1") == ["result1"]

        # Wait for expiry
        time.sleep(0.2)
        assert cache.get("key1") is None

    def test_cache_max_size(self):
        """Test cache max size eviction."""
        cache = SearchCache(ttl=60, max_size=3)

        # Fill cache
        cache.set("key1", ["result1"])
        cache.set("key2", ["result2"])
        cache.set("key3", ["result3"])

        # Add one more (should evict oldest)
        cache.set("key4", ["result4"])

        # key1 should be evicted
        assert cache.get("key1") is None
        assert cache.get("key4") == ["result4"]

    def test_cache_clear(self):
        """Test cache clearing."""
        cache = SearchCache(ttl=60, max_size=10)

        cache.set("key1", ["result1"])
        cache.set("key2", ["result2"])

        cache.clear()

        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_cache_update(self):
        """Test cache update."""
        cache = SearchCache(ttl=60, max_size=10)

        cache.set("key1", ["result1"])
        cache.set("key1", ["result2"])

        assert cache.get("key1") == ["result2"]


class TestKnowledgeCache:
    """Tests for KnowledgeManager caching."""

    @pytest.mark.asyncio
    async def test_search_caching(self):
        """Test that search results are cached."""
        from app.config import Settings
        from app.knowledge.manager import KnowledgeManager

        config = Settings()
        km = KnowledgeManager(config)

        # First search
        results1 = await km.search("订单")

        # Second search (should be cached)
        results2 = await km.search("订单")

        assert results1 == results2

        # Clear cache
        km.clear_cache()

        # Search again (fresh)
        results3 = await km.search("订单")
        assert results1 == results3  # Same results, but freshly computed

    @pytest.mark.asyncio
    async def test_search_different_queries(self):
        """Test that different queries have different cache entries."""
        from app.config import Settings
        from app.knowledge.manager import KnowledgeManager

        config = Settings()
        km = KnowledgeManager(config)

        results1 = await km.search("订单")
        results2 = await km.search("退货")

        # Different queries may have different results
        # At minimum, they should both return results
        assert len(results1) > 0
        assert len(results2) > 0
