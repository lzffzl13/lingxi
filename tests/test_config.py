from app.config import Settings
import pytest


def test_default_config():
    """Test that config loads with default values."""
    config = Settings(LLM_API_KEY="test-key")
    assert config.APP_NAME == "lingxi-service"
    assert config.SESSION_TTL == 3600
    assert config.KNOWLEDGE_TOP_K == 3


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


def test_auth_enabled_requires_api_key():
    """Auth cannot be enabled with a blank API key."""
    with pytest.raises(ValueError, match="API_KEY must be set"):
        Settings(LLM_API_KEY="test-key", AUTH_ENABLED=True, API_KEY="   ")


def test_production_requires_auth_enabled():
    """Production must not run with auth disabled."""
    with pytest.raises(ValueError, match="AUTH_ENABLED must be true in production"):
        Settings(
            LLM_API_KEY="test-key",
            APP_ENV="production",
            AUTH_ENABLED=False,
            API_KEY="custom-secure-key",
        )


def test_production_requires_non_default_api_key():
    """Production must not run with the default API key."""
    with pytest.raises(ValueError, match="API_KEY must be changed in production"):
        Settings(
            LLM_API_KEY="test-key",
            APP_ENV="production",
            AUTH_ENABLED=True,
        )
