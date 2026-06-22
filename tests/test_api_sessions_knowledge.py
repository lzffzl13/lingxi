"""Direct tests for sessions and knowledge API handlers."""

import json
from unittest.mock import AsyncMock

import pytest

from app.api.knowledge import (
    FAQCreate,
    FAQUpdate,
    SearchRequest,
    create_faq,
    delete_faq,
    get_faq,
    list_faqs,
    search_knowledge,
    update_faq,
)
from app.api.sessions import delete_session, get_session, get_session_slots, list_sessions
from app.exceptions import FAQNotFoundError, SessionNotFoundError
from app.knowledge.manager import FAQ_DATABASE


class FakeSessionRedis:
    def __init__(self):
        self.histories = {}
        self.slots = {}
        self.deleted = []

    async def scan_iter(self, pattern):
        for key in self.histories:
            if key.startswith("session:") and key.endswith(":history"):
                yield key

    async def llen(self, key):
        return len(self.histories.get(key, []))

    async def exists(self, key):
        return int(key in self.histories or key in self.slots)

    async def lrange(self, key, start, end):
        return list(self.histories.get(key, []))

    async def hgetall(self, key):
        return dict(self.slots.get(key, {}))

    async def delete(self, key):
        self.deleted.append(key)
        self.histories.pop(key, None)
        self.slots.pop(key, None)


@pytest.fixture
def session_redis():
    redis = FakeSessionRedis()
    redis.histories["session:s1:history"] = [
        json.dumps({"role": "user", "content": "hello"})
    ]
    redis.histories["session:s2:history"] = []
    redis.slots["session:s1:slots"] = {"order_id": "ORD-1"}
    return redis


@pytest.mark.asyncio
async def test_list_sessions(session_redis):
    sessions = await list_sessions(session_redis)

    assert {session.session_id for session in sessions} == {"s1", "s2"}
    s1 = next(session for session in sessions if session.session_id == "s1")
    assert s1.message_count == 1
    assert s1.has_slots is True


@pytest.mark.asyncio
async def test_get_session_returns_history(session_redis):
    session = await get_session("s1", session_redis)

    assert session.session_id == "s1"
    assert session.messages == [{"role": "user", "content": "hello"}]


@pytest.mark.asyncio
async def test_session_handlers_raise_for_missing_session(session_redis):
    with pytest.raises(SessionNotFoundError):
        await get_session("missing", session_redis)

    with pytest.raises(SessionNotFoundError):
        await delete_session("missing", session_redis)

    with pytest.raises(SessionNotFoundError):
        await get_session_slots("missing", session_redis)


@pytest.mark.asyncio
async def test_delete_session_removes_history_and_slots(session_redis):
    response = await delete_session("s1", session_redis)

    assert response == {"message": "Session s1 deleted"}
    assert session_redis.deleted == ["session:s1:history", "session:s1:slots"]


@pytest.mark.asyncio
async def test_get_session_slots(session_redis):
    response = await get_session_slots("s1", session_redis)

    assert response == {"session_id": "s1", "slots": {"order_id": "ORD-1"}}


@pytest.fixture
def isolated_faq_database():
    original = list(FAQ_DATABASE)
    FAQ_DATABASE[:] = [
        {
            "question": "Q1",
            "answer": "A1",
            "category": "general",
            "keywords": ["q1"],
        }
    ]
    yield
    FAQ_DATABASE[:] = original


@pytest.mark.asyncio
async def test_faq_crud_handlers(isolated_faq_database):
    faqs = await list_faqs()
    assert len(faqs) == 1
    assert faqs[0].id == 0

    faq = await get_faq(0)
    assert faq.question == "Q1"

    created = await create_faq(
        FAQCreate(question="Q2", answer="A2", category="cat", keywords=["k"])
    )
    assert created.id == 1
    assert created.keywords == ["k"]

    updated = await update_faq(1, FAQUpdate(answer="A2 updated", keywords=["new"]))
    assert updated.question == "Q2"
    assert updated.answer == "A2 updated"
    assert updated.keywords == ["new"]

    response = await delete_faq(1)
    assert response == {"message": "FAQ 1 deleted"}
    assert len(FAQ_DATABASE) == 1


@pytest.mark.asyncio
async def test_faq_handlers_raise_for_missing_id(isolated_faq_database):
    with pytest.raises(FAQNotFoundError):
        await get_faq(99)

    with pytest.raises(FAQNotFoundError):
        await update_faq(99, FAQUpdate(question="missing"))

    with pytest.raises(FAQNotFoundError):
        await delete_faq(99)


@pytest.mark.asyncio
async def test_search_knowledge_handler():
    manager = AsyncMock()
    manager.search.return_value = [{"question": "Q", "score": 1.0}]

    response = await search_knowledge(SearchRequest(query="q", top_k=5), manager)

    assert response == {"query": "q", "results": [{"question": "Q", "score": 1.0}]}
    manager.search.assert_awaited_once_with("q", 5)
