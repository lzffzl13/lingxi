"""API endpoint tests."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, MagicMock

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


def override_agent(api_app, agent):
    """Override chat endpoint agent dependency."""
    from app.api.deps import get_agent

    api_app.dependency_overrides[get_agent] = lambda: agent


@pytest.mark.asyncio
async def test_health_ok(api_app, client):
    """Health endpoint reports ok when Redis and LLM are available."""
    override_health_deps(api_app, redis_ok=True, llm_ok=True)

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
    override_health_deps(api_app, redis_ok=True, llm_ok=False)

    resp = await client.get("/health")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "degraded"
    assert data["redis"] == "connected"
    assert data["llm"] == "unavailable"


@pytest.mark.asyncio
async def test_health_unhealthy(api_app, client):
    """Health endpoint reports unhealthy when required dependencies fail."""
    override_health_deps(api_app, redis_ok=False, llm_ok=False)

    resp = await client.get("/health")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "unhealthy"
    assert data["redis"] == "disconnected"
    assert data["llm"] == "unavailable"


@pytest.mark.asyncio
async def test_chat_success(api_app, client):
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
async def test_chat_rejects_empty_after_sanitize(api_app, client):
    """Chat endpoint rejects messages that are empty after sanitization."""
    mock_agent = AsyncMock()
    override_agent(api_app, mock_agent)

    resp = await client.post(
        "/chat",
        json={"session_id": "test-001", "message": "   "},
    )

    assert resp.status_code == 400
    assert resp.json()["detail"] == "Message cannot be empty"
    mock_agent.run.assert_not_called()


@pytest.mark.asyncio
async def test_chat_rejects_too_long_message(api_app, client):
    """Chat endpoint rejects messages beyond the configured limit."""
    mock_agent = AsyncMock()
    override_agent(api_app, mock_agent)

    resp = await client.post(
        "/chat",
        json={"session_id": "test-001", "message": "x" * 2001},
    )

    assert resp.status_code == 422
    mock_agent.run.assert_not_called()


@pytest.mark.asyncio
async def test_chat_agent_error_returns_500(api_app, client):
    """Chat endpoint hides unexpected agent errors behind a 500 response."""
    mock_agent = AsyncMock()
    mock_agent.run.side_effect = RuntimeError("boom")
    override_agent(api_app, mock_agent)

    resp = await client.post(
        "/chat",
        json={"session_id": "test-001", "message": "hello"},
    )

    assert resp.status_code == 500
    assert resp.json()["detail"] == "Internal server error"


@pytest.mark.asyncio
async def test_chat_stream(api_app, client):
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
        json={"session_id": "test-001", "message": "hello"},
    )

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert "event: token" in resp.text
    assert "event: done" in resp.text


@pytest.mark.asyncio
async def test_cache_stats_and_clear(client):
    """Cache endpoints expose stats and clear cached responses."""
    from app.cache import init_response_cache

    cache = init_response_cache(max_size=2, ttl_seconds=30)
    cache.set([{"role": "user", "content": "hello"}], "cached")

    stats_resp = await client.get("/cache/stats")
    assert stats_resp.status_code == 200
    assert stats_resp.json()["size"] == 1

    clear_resp = await client.post("/cache/clear")
    assert clear_resp.status_code == 200
    assert clear_resp.json()["message"] == "Cache cleared successfully"
    assert cache.size() == 0
