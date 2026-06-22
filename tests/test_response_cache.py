"""Response cache tests."""

import time

from app.cache.response_cache import ResponseCache, init_response_cache, get_response_cache


def test_response_cache_set_and_get():
    cache = ResponseCache(max_size=3, ttl_seconds=60)
    messages = [{"role": "user", "content": "hello"}]

    cache.set(messages, "hi")

    assert cache.get(messages) == "hi"
    assert cache.size() == 1


def test_response_cache_miss_for_different_messages():
    cache = ResponseCache(max_size=3, ttl_seconds=60)
    cache.set([{"role": "user", "content": "hello"}], "hi")

    assert cache.get([{"role": "user", "content": "different"}]) is None


def test_response_cache_expires_entries():
    cache = ResponseCache(max_size=3, ttl_seconds=0.01)
    messages = [{"role": "user", "content": "hello"}]
    cache.set(messages, "hi")

    time.sleep(0.02)

    assert cache.get(messages) is None
    assert cache.size() == 0


def test_response_cache_evicts_least_recently_used_entry():
    cache = ResponseCache(max_size=2, ttl_seconds=60)
    first = [{"role": "user", "content": "first"}]
    second = [{"role": "user", "content": "second"}]
    third = [{"role": "user", "content": "third"}]

    cache.set(first, "1")
    cache.set(second, "2")
    assert cache.get(first) == "1"
    cache.set(third, "3")

    assert cache.get(first) == "1"
    assert cache.get(second) is None
    assert cache.get(third) == "3"


def test_response_cache_includes_tool_calls_in_key():
    cache = ResponseCache(max_size=3, ttl_seconds=60)
    messages = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"id": "call-1", "function": {"name": "check_order"}}],
        }
    ]
    same_content_different_tool = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"id": "call-2", "function": {"name": "check_order"}}],
        }
    ]

    cache.set(messages, "tool response")

    assert cache.get(messages) == "tool response"
    assert cache.get(same_content_different_tool) is None


def test_response_cache_stats_and_clear():
    cache = ResponseCache(max_size=3, ttl_seconds=60)
    cache.set([{"role": "user", "content": "hello"}], "hi")

    stats = cache.stats()
    assert stats["size"] == 1
    assert stats["max_size"] == 3
    assert stats["ttl_seconds"] == 60
    assert stats["expired_entries"] == 0

    cache.clear()
    assert cache.size() == 0


def test_global_response_cache_can_be_initialized():
    cache = init_response_cache(max_size=5, ttl_seconds=10)

    assert get_response_cache() is cache
    assert cache.stats()["max_size"] == 5
    assert cache.stats()["ttl_seconds"] == 10
