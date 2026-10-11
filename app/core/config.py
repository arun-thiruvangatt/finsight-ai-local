from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "FinSight AI"
    APP_ENV: str = "development"
    DEBUG: bool = False

    DATABASE_URL: str = "postgresql+psycopg://postgres:qwe123r456@localhost:5432/finsight"
    REDIS_URL: str = "redis://localhost:6379/0"

    JWT_SECRET_KEY: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    LLM_PROVIDER: str = "openai"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "qwen2.5:1.5b"
    LLM_BASE_URL: str = "http://localhost:11434/v1"

    EMBEDDING_PROVIDER: str = ""
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_MODEL: str = ""
    EMBEDDING_BASE_URL: str = ""
    EMBEDDING_DIM: int = 384

    CORS_ORIGINS: str = "http://localhost:5173"
    MAX_UPLOAD_SIZE_MB: int = 20
    UPLOAD_DIR: str = "./uploads"

    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_AI_PER_MINUTE: int = 20
    RATE_LIMIT_UPLOAD_PER_MINUTE: int = 10

    CELERY_EAGER: bool = False  # run tasks inline (tests / no worker)
    AUTO_CATEGORIZE_WITH_LLM: bool = True

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() in {"production", "prod"}

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @model_validator(mode="after")
    def _check_secrets(self) -> "Settings":
        if self.is_production and (self.JWT_SECRET_KEY in {"", "change-me"} or len(self.JWT_SECRET_KEY) < 32):
            raise ValueError("JWT_SECRET_KEY must be a random value of >= 32 chars in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
