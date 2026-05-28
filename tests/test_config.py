import pytest
from app.config import Settings


def test_default_config():
    """Test that config loads with default values."""
    config = Settings(LLM_API_KEY="test-key")
    assert config.APP_NAME == "lingxi-service"
    assert config.LLM_MODEL == "deepseek-chat"
    assert config.REDIS_URL == "redis://localhost:6379/0"
    assert config.SESSION_TTL == 3600


def test_custom_config():
    """Test that config accepts custom values."""
    config = Settings(
        LLM_API_KEY="test-key",
        LLM_MODEL="gpt-4",
        REDIS_URL="redis://custom:6379/1",
    )
    assert config.LLM_MODEL == "gpt-4"
    assert config.REDIS_URL == "redis://custom:6379/1"


def test_secret_key():
    """Test that API key is stored as SecretStr."""
    config = Settings(LLM_API_KEY="my-secret-key")
    assert config.LLM_API_KEY.get_secret_value() == "my-secret-key"
