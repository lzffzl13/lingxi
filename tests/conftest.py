import pytest
from unittest.mock import AsyncMock, MagicMock
from app.config import Settings


@pytest.fixture
def test_config():
    """Test configuration with mock values."""
    return Settings(
        LLM_API_KEY="test-key",
        LLM_BASE_URL="http://localhost:9999/v1",
        LLM_MODEL="test-model",
        REDIS_URL="redis://localhost:6379/1",
    )


@pytest.fixture
def mock_llm_client():
    """Mock LLM client returning preset responses."""
    client = AsyncMock()
    default_response = MagicMock()
    default_response.choices = [MagicMock()]
    default_response.choices[0].finish_reason = "stop"
    default_response.choices[0].message.content = "你好！有什么可以帮您的吗？"
    default_response.choices[0].message.tool_calls = None
    client.chat.return_value = default_response
    return client
