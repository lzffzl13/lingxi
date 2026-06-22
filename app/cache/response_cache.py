"""Response cache for LLM answers to reduce API calls."""

import hashlib
import json
import time
from collections import OrderedDict
from typing import Optional


class ResponseCache:
    """LRU cache for LLM responses.

    Features:
    - LRU eviction policy
    - TTL-based expiration
    - Max size limit
    - Cache key based on message history
    """

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        self._cache: OrderedDict[str, tuple[str, float]] = OrderedDict()
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds

    def _generate_key(self, messages: list[dict]) -> str:
        """Generate cache key from message history."""
        # Create a deterministic string from messages
        key_parts = []
        for msg in messages:
            role = msg.get('role', '')
            content = msg.get('content', '')
            # Include tool calls in key if present
            tool_calls = msg.get('tool_calls', [])
            if tool_calls:
                tool_str = json.dumps(tool_calls, sort_keys=True)
                key_parts.append(f"{role}:{content}:{tool_str}")
            else:
                key_parts.append(f"{role}:{content}")

        key_string = "|".join(key_parts)
        return hashlib.sha256(key_string.encode()).hexdigest()

    def get(self, messages: list[dict]) -> Optional[str]:
        """Get cached response for messages.

        Returns None if not found or expired.
        """
        key = self._generate_key(messages)

        if key not in self._cache:
            return None

        response, timestamp = self._cache[key]

        # Check TTL
        if time.time() - timestamp > self._ttl_seconds:
            # Expired, remove from cache
            del self._cache[key]
            return None

        # Move to end (most recently used)
        self._cache.move_to_end(key)
        return response

    def set(self, messages: list[dict], response: str) -> None:
        """Cache response for messages."""
        key = self._generate_key(messages)

        # If key exists, update and move to end
        if key in self._cache:
            self._cache.move_to_end(key)

        # Add new entry
        self._cache[key] = (response, time.time())

        # Evict oldest if over max size
        while len(self._cache) > self._max_size:
            self._cache.popitem(last=False)

    def clear(self) -> None:
        """Clear all cached responses."""
        self._cache.clear()

    def size(self) -> int:
        """Get current cache size."""
        return len(self._cache)

    def stats(self) -> dict:
        """Get cache statistics."""
        now = time.time()
        expired_count = sum(
            1 for _, (_, ts) in self._cache.items()
            if now - ts > self._ttl_seconds
        )
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "ttl_seconds": self._ttl_seconds,
            "expired_entries": expired_count,
        }


# Global cache instance
_response_cache: Optional[ResponseCache] = None


def get_response_cache() -> ResponseCache:
    """Get global response cache instance."""
    global _response_cache
    if _response_cache is None:
        _response_cache = ResponseCache(max_size=1000, ttl_seconds=3600)
    return _response_cache


def init_response_cache(max_size: int = 1000, ttl_seconds: int = 3600) -> ResponseCache:
    """Initialize global response cache with custom settings."""
    global _response_cache
    _response_cache = ResponseCache(max_size=max_size, ttl_seconds=ttl_seconds)
    return _response_cache
