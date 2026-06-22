"""Session manager tests."""

import json
from datetime import datetime

import pytest

from app.config import Settings
from app.models.message import Message, MessageRole
from app.session.manager import SessionManager


class FakeRedis:
    """Small async Redis fake for session manager behavior."""

    def __init__(self):
        self.lists = {}
        self.hashes = {}
        self.expirations = {}
        self.deleted = []

    async def lrange(self, key, start, end):
        values = self.lists.get(key, [])
        if start == 0 and end == -1:
            return list(values)
        return values[start : end + 1]

    async def rpush(self, key, value):
        self.lists.setdefault(key, []).append(value)

    async def ltrim(self, key, start, end):
        values = self.lists.get(key, [])
        if start < 0:
            start = max(len(values) + start, 0)
        if end < 0:
            end = len(values) + end
        self.lists[key] = values[start : end + 1]

    async def hgetall(self, key):
        return dict(self.hashes.get(key, {}))

    async def hset(self, key, mapping):
        self.hashes.setdefault(key, {}).update(mapping)

    async def delete(self, *keys):
        self.deleted.extend(keys)
        for key in keys:
            self.lists.pop(key, None)
            self.hashes.pop(key, None)

    async def expire(self, key, ttl):
        self.expirations[key] = ttl


@pytest.fixture
def session_manager():
    redis = FakeRedis()
    config = Settings(SESSION_TTL=30, MAX_HISTORY_LENGTH=2)
    return SessionManager(redis, config), redis


@pytest.mark.asyncio
async def test_append_message_trims_history_and_refreshes_ttl(session_manager):
    manager, redis = session_manager

    await manager.append_message("s1", Message(role=MessageRole.USER, content="one"))
    await manager.append_message("s1", Message(role=MessageRole.ASSISTANT, content="two"))
    await manager.append_message("s1", Message(role=MessageRole.USER, content="three"))

    history = await manager.get_history("s1")
    assert [msg.content for msg in history] == ["two", "three"]
    assert redis.expirations["session:s1:history"] == 30
    assert redis.expirations["session:s1:slots"] == 30


@pytest.mark.asyncio
async def test_get_history_deserializes_timestamps(session_manager):
    manager, redis = session_manager
    redis.lists["session:s1:history"] = [
        json.dumps(
            {
                "role": "user",
                "content": "hello",
                "timestamp": "2026-01-01T12:00:00",
                "tool_call_id": None,
                "tool_name": None,
            }
        )
    ]

    history = await manager.get_history("s1")

    assert history[0].role == MessageRole.USER
    assert history[0].content == "hello"
    assert isinstance(history[0].timestamp, datetime)


@pytest.mark.asyncio
async def test_get_slots_returns_default_when_empty(session_manager):
    manager, _ = session_manager

    slots = await manager.get_slots("s1")

    assert slots.transferred is False
    assert slots.order_id is None
    assert slots.collected_info == {}


@pytest.mark.asyncio
async def test_update_slot_round_trips_json_values(session_manager):
    manager, redis = session_manager

    slots = await manager.update_slot(
        "s1",
        order_id="ORD-1",
        transferred=True,
        collected_info={"email": "a@example.com"},
    )

    assert slots.order_id == "ORD-1"
    assert slots.transferred is True
    assert slots.collected_info == {"email": "a@example.com"}
    assert json.loads(redis.hashes["session:s1:slots"]["transferred"]) is True


@pytest.mark.asyncio
async def test_get_slots_keeps_plain_values_when_not_json(session_manager):
    manager, redis = session_manager
    redis.hashes["session:s1:slots"] = {"order_id": "ORD-1"}

    slots = await manager.get_slots("s1")

    assert slots.order_id == "ORD-1"


@pytest.mark.asyncio
async def test_clear_session_deletes_history_and_slots(session_manager):
    manager, redis = session_manager

    await manager.clear_session("s1")

    assert redis.deleted == ["session:s1:history", "session:s1:slots"]
