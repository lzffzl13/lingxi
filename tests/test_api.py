import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_health():
    """Test health endpoint returns valid response."""
    with patch("app.main.get_redis_client") as mock_redis, \
         patch("app.main.get_agent") as mock_agent:

        mock_redis.return_value.ping = AsyncMock()
        mock_agent.return_value.llm.health_check = AsyncMock(return_value=True)

        from app.main import app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] in ("ok", "degraded")


@pytest.mark.asyncio
async def test_chat():
    """Test chat endpoint returns valid response."""
    mock_response = MagicMock()
    mock_response.session_id = "test-001"
    mock_response.reply = "你好！"
    mock_response.status = "active"
    mock_response.tool_calls_made = []

    with patch("app.main.get_agent") as mock_get_agent:
        mock_agent = AsyncMock()
        mock_agent.run.return_value = mock_response
        mock_get_agent.return_value = mock_agent

        from app.main import app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/chat", json={
                "session_id": "test-001",
                "message": "你好",
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["session_id"] == "test-001"
            assert len(data["reply"]) > 0
