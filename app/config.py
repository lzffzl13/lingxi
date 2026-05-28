from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    APP_NAME: str = "lingxi-service"
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"

    # LLM
    LLM_API_KEY: SecretStr = SecretStr("not-set")
    LLM_BASE_URL: str = "https://api.deepseek.com/v1"
    LLM_MODEL: str = "deepseek-chat"
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 1024

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Session
    SESSION_TTL: int = 3600
    MAX_HISTORY_LENGTH: int = 20


settings = Settings()
