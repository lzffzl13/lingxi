from pydantic import SecretStr
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_API_KEY = "lingxi-api-key-change-me"


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
    VERSION: str = "1.2.0"
    PORT: int = 8002

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

    # Knowledge Base
    CHROMA_PERSIST_DIR: str = "./data/chroma"
    VECTOR_BACKEND: str = "qdrant"
    VECTOR_PERSIST_DIRECTORY: str = "./data/rag_vectors"
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: SecretStr = SecretStr("not-set")
    QDRANT_COLLECTION: str = "faq_knowledge"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSION: int = 1536
    EMBEDDING_BASE_URL: str = "https://api.openai.com/v1"
    EMBEDDING_API_KEY: SecretStr = SecretStr("not-set")
    EMBEDDING_LOCAL_MODEL: str = "all-MiniLM-L6-v2"
    EMBEDDING_CACHE_ENABLED: bool = True
    EMBEDDING_CACHE_TTL_SECONDS: int = 2592000
    KNOWLEDGE_TOP_K: int = 3

    # Database (MySQL)
    DATABASE_URL: str = ""

    # Security
    API_KEY: str = DEFAULT_API_KEY
    AUTH_ENABLED: bool = True
    CORS_ORIGINS: list[str] = ["*"]
    RATE_LIMIT: str = "100/minute"

    # Agent
    MAX_ITERATIONS: int = 5
    HISTORY_WINDOW: int = 10

    # LLM Retry
    LLM_MAX_RETRIES: int = 3
    LLM_RETRY_DELAY: float = 1.0
    LLM_REQUEST_TIMEOUT: float = 60.0

    # Cache
    CACHE_MAX_SIZE: int = 1000
    CACHE_TTL_SECONDS: int = 3600

    # Security
    MAX_MESSAGE_LENGTH: int = 10000
    MAX_REQUEST_SIZE: int = 1048576  # 1MB

    @model_validator(mode="after")
    def validate_security_settings(self):
        """Fail fast when auth settings are unsafe."""
        if self.AUTH_ENABLED and not self.API_KEY.strip():
            raise ValueError("API_KEY must be set when AUTH_ENABLED is true")

        if self.APP_ENV == "production":
            if not self.AUTH_ENABLED:
                raise ValueError("AUTH_ENABLED must be true in production")
            if self.API_KEY == DEFAULT_API_KEY:
                raise ValueError("API_KEY must be changed in production")

        return self


settings = Settings()
