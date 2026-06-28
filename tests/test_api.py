"""API endpoint tests."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, MagicMock

from app.config import DEFAULT_API_KEY
from app.models.schemas import ChatResponse


@pytest.fixture
def api_app():
    """Return the FastAPI app and clear dependency overrides after each test."""
    from app.main import app

    yield app
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(api_app):
    """HTTP client backed by the ASGI app."""
    transport = ASGITransport(app=api_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def auth_headers():
    """Default authenticated headers for protected endpoints."""
    return {"X-API-Key": DEFAULT_API_KEY}


def override_health_deps(api_app, redis_ok=True, llm_ok=True):
    """Override health endpoint dependencies."""
    from app.api.deps import get_agent, get_redis

    mock_redis = AsyncMock()
    if redis_ok:
        mock_redis.ping.return_value = True
    else:
        mock_redis.ping.side_effect = RuntimeError("redis down")

    mock_agent = AsyncMock()
    if llm_ok:
        mock_agent.llm.health_check.return_value = True
    else:
        mock_agent.llm.health_check.side_effect = RuntimeError("llm down")

    api_app.dependency_overrides[get_redis] = lambda: mock_redis
    api_app.dependency_overrides[get_agent] = lambda: mock_agent
    return mock_redis, mock_agent


class _FakeSession:
    def __init__(self, should_fail=False):
        self.should_fail = should_fail

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def execute(self, _query):
        if self.should_fail:
            raise RuntimeError("db down")
        return 1


def make_session_factory(should_fail=False):
    def factory():
        return _FakeSession(should_fail=should_fail)

    return factory


def override_agent(api_app, agent):
    """Override chat endpoint agent dependency."""
    from app.api.deps import get_agent

    api_app.dependency_overrides[get_agent] = lambda: agent


@pytest.mark.asyncio
async def test_health_ok(api_app, client):
    """Health endpoint reports ok when Redis and LLM are available."""
    from app.api import health as health_module

    override_health_deps(api_app, redis_ok=True, llm_ok=True)
    health_module.settings.DATABASE_URL = ""
    health_module.async_session_factory = None

    resp = await client.get("/health")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["redis"] == "connected"
    assert data["llm"] == "available"
    assert "version" in data
    assert "database" in data


@pytest.mark.asyncio
async def test_health_degraded(api_app, client):
    """Health endpoint reports degraded when one dependency is unavailable."""
    from app.api import health as health_module

    override_health_deps(api_app, redis_ok=True, llm_ok=False)
    health_module.settings.DATABASE_URL = ""
    health_module.async_session_factory = None

    resp = await client.get("/health")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "degraded"
    assert data["redis"] == "connected"
    assert data["llm"] == "unavailable"


@pytest.mark.asyncio
async def test_health_unhealthy(api_app, client):
    """Health endpoint reports unhealthy when required dependencies fail."""
    from app.api import health as health_module

    override_health_deps(api_app, redis_ok=False, llm_ok=False)
    health_module.settings.DATABASE_URL = ""
    health_module.async_session_factory = None

    resp = await client.get("/health")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "unhealthy"
    assert data["redis"] == "disconnected"
    assert data["llm"] == "unavailable"


@pytest.mark.asyncio
async def test_health_degraded_when_database_is_configured_but_unavailable(api_app, client):
    """Database failures should degrade overall health when DB is configured."""
    from app.api import health as health_module

    override_health_deps(api_app, redis_ok=True, llm_ok=True)
    health_module.settings.DATABASE_URL = "mysql+aiomysql://user:pass@localhost/db"
    health_module.async_session_factory = make_session_factory(should_fail=True)

    resp = await client.get("/health")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "degraded"
    assert data["database"] == "unavailable"


@pytest.mark.asyncio
async def test_health_ok_when_database_is_connected(api_app, client):
    """Database connectivity should be reflected in both component and overall status."""
    from app.api import health as health_module

    override_health_deps(api_app, redis_ok=True, llm_ok=True)
    health_module.settings.DATABASE_URL = "mysql+aiomysql://user:pass@localhost/db"
    health_module.async_session_factory = make_session_factory(should_fail=False)

    resp = await client.get("/health")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"


@pytest.mark.asyncio
async def test_chat_success(api_app, client, auth_headers):
    """Chat endpoint returns the agent response."""
    mock_agent = AsyncMock()
    mock_agent.run.return_value = ChatResponse(
        session_id="test-001",
        reply="Hello, how can I help?",
        status="active",
        tool_calls_made=[],
    )
    override_agent(api_app, mock_agent)

    resp = await client.post(
        "/chat",
        headers=auth_headers,
        json={"session_id": "test-001", "message": "hello"},
    )

    assert resp.status_code == 200
    assert resp.json() == {
        "session_id": "test-001",
        "reply": "Hello, how can I help?",
        "status": "active",
        "tool_calls_made": [],
    }
    mock_agent.run.assert_awaited_once_with(
        session_id="test-001",
        user_message="hello",
    )


@pytest.mark.asyncio
async def test_chat_rejects_empty_after_sanitize(api_app, client, auth_headers):
    """Chat endpoint rejects messages that are empty after sanitization."""
    mock_agent = AsyncMock()
    override_agent(api_app, mock_agent)

    resp = await client.post(
        "/chat",
        headers=auth_headers,
        json={"session_id": "test-001", "message": "   "},
    )

    assert resp.status_code == 400
    assert resp.json()["detail"] == "Message cannot be empty"
    mock_agent.run.assert_not_called()


@pytest.mark.asyncio
async def test_chat_rejects_too_long_message(api_app, client, auth_headers):
    """Chat endpoint rejects messages beyond the configured limit."""
    mock_agent = AsyncMock()
    override_agent(api_app, mock_agent)

    resp = await client.post(
        "/chat",
        headers=auth_headers,
        json={"session_id": "test-001", "message": "x" * 2001},
    )

    assert resp.status_code == 422
    mock_agent.run.assert_not_called()


@pytest.mark.asyncio
async def test_chat_agent_error_returns_500(api_app, client, auth_headers):
    """Chat endpoint hides unexpected agent errors behind a 500 response."""
    mock_agent = AsyncMock()
    mock_agent.run.side_effect = RuntimeError("boom")
    override_agent(api_app, mock_agent)

    resp = await client.post(
        "/chat",
        headers=auth_headers,
        json={"session_id": "test-001", "message": "hello"},
    )

    assert resp.status_code == 500
    assert resp.json()["detail"] == "Internal server error"


@pytest.mark.asyncio
async def test_chat_stream(api_app, client, auth_headers):
    """Streaming chat endpoint returns server-sent events from the agent."""
    async def event_source(session_id, user_message):
        assert session_id == "test-001"
        assert user_message == "hello"
        yield "event: token\ndata: hi\n\n"
        yield "event: done\ndata: {}\n\n"

    mock_agent = MagicMock()
    mock_agent.run_stream.side_effect = event_source
    override_agent(api_app, mock_agent)

    resp = await client.post(
        "/chat/stream",
        headers=auth_headers,
        json={"session_id": "test-001", "message": "hello"},
    )

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert "event: token" in resp.text
    assert "event: done" in resp.text


@pytest.mark.asyncio
async def test_chat_stream_persists_partial_reply_on_disconnect():
    """Streaming endpoint persists partial assistant output when the client disconnects early."""
    from app.api.chat import chat_stream
    from app.models.schemas import ChatRequest

    async def event_source(session_id, user_message):
        assert session_id == "test-001"
        assert user_message == "hello"
        yield 'event: token\ndata: {"content": "partial"}\n\n'
        yield 'event: token\ndata: {"content": " ignored"}\n\n'

    mock_agent = MagicMock()
    mock_agent.run_stream.side_effect = event_source
    mock_agent.record_stream_interruption = AsyncMock()

    response = await chat_stream(
        ChatRequest(session_id="test-001", message="hello"),
        mock_agent,
    )

    first_event = await anext(response.body_iterator)
    assert "partial" in first_event
    await response.body_iterator.aclose()

    mock_agent.record_stream_interruption.assert_awaited_once_with(
        session_id="test-001",
        partial_reply="partial",
        tool_calls_made=None,
    )


@pytest.mark.asyncio
async def test_cache_stats_and_clear(client, auth_headers):
    """Cache endpoints expose stats and clear cached responses."""
    from app.cache import init_response_cache

    cache = init_response_cache(max_size=2, ttl_seconds=30)
    cache.set([{"role": "user", "content": "hello"}], "cached")

    stats_resp = await client.get("/cache/stats", headers=auth_headers)
    assert stats_resp.status_code == 200
    assert stats_resp.json()["size"] == 1

    clear_resp = await client.post("/cache/clear", headers=auth_headers)
    assert clear_resp.status_code == 200
    assert clear_resp.json()["message"] == "Cache cleared successfully"
    assert cache.size() == 0


@pytest.mark.asyncio
async def test_protected_endpoint_requires_api_key(api_app, client):
    """Protected endpoints reject requests without an API key."""
    override_agent(api_app, AsyncMock())

    resp = await client.post(
        "/chat",
        json={"session_id": "test-001", "message": "hello"},
    )

    assert resp.status_code == 401
    assert resp.json()["code"] == "MISSING_API_KEY"


@pytest.mark.asyncio
async def test_query_param_api_key_is_not_accepted(api_app, client):
    """Protected endpoints must reject API keys passed in the query string."""
    override_agent(api_app, AsyncMock())

    resp = await client.post(
        "/chat?api_key=lingxi-api-key-change-me",
        json={"session_id": "test-001", "message": "hello"},
    )

    assert resp.status_code == 401
    assert resp.json()["code"] == "MISSING_API_KEY"
