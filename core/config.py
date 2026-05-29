from functools import lru_cache
from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from core.constants import STREAM_TEXT_PREVIEW_MAX_CHARS

LOCAL_ADMIN_TOKEN = "local-admin-token"
LOCAL_INTERNAL_TOKEN = "local-internal-token"
LOCAL_ADMIN_DATABASE_URL = (
    "postgresql+psycopg://"
    + "agent_support_admin"
    + ":"
    + "agent_support_admin"
    + "@localhost:5432/agent_support"
)
LOCAL_APP_DATABASE_URL = (
    "postgresql+psycopg://"
    + "agent_support_app"
    + ":"
    + "agent_support_app"
    + "@localhost:5432/agent_support"
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AGENT_SUPPORT_", extra="ignore")

    service_name: str = "Agent Support"
    service_version: str = "0.1.0"
    environment: str = "local"
    admin_token: str = LOCAL_ADMIN_TOKEN
    internal_token: str = LOCAL_INTERNAL_TOKEN
    database_admin_url: str = Field(default=LOCAL_ADMIN_DATABASE_URL)
    database_url: str = Field(default=LOCAL_APP_DATABASE_URL)
    redis_url: str = "redis://localhost:6379/0"
    redis_stream_max_length: int = Field(default=100_000, gt=0)
    redis_publish_timeout_seconds: float = Field(default=1.0, gt=0)
    redis_memory_warn_ratio: float = Field(default=0.80, gt=0, lt=1)
    redis_memory_reject_ratio: float = Field(default=0.90, gt=0, lt=1)
    redis_pending_reject_limit: int = Field(default=10_000, gt=0)
    redis_pending_idle_reclaim_seconds: int = Field(default=300, gt=0)
    redis_ingress_consumer_group: str = Field(default="message-stub", min_length=1)
    redis_text_preview_max_chars: int = Field(
        default=STREAM_TEXT_PREVIEW_MAX_CHARS,
        gt=0,
        le=STREAM_TEXT_PREVIEW_MAX_CHARS,
    )
    redis_consumer_block_ms: int = Field(default=5_000, gt=0)
    redis_consumer_batch_size: int = Field(default=10, gt=0)
    redis_connection_pool_size: int = Field(default=10, gt=0)
    qdrant_url: str = "http://localhost:6333"

    @model_validator(mode="after")
    def reject_default_admin_token_outside_local(self) -> Self:
        if (
            self.environment.casefold() in {"production", "prod", "staging"}
            and self.admin_token == LOCAL_ADMIN_TOKEN
        ):
            raise ValueError("AGENT_SUPPORT_ADMIN_TOKEN must be changed outside local env")
        if (
            self.environment.casefold() in {"production", "prod", "staging"}
            and self.internal_token == LOCAL_INTERNAL_TOKEN
        ):
            raise ValueError("AGENT_SUPPORT_INTERNAL_TOKEN must be changed outside local env")
        if self.redis_memory_warn_ratio >= self.redis_memory_reject_ratio:
            raise ValueError(
                "AGENT_SUPPORT_REDIS_MEMORY_WARN_RATIO must be lower than "
                "AGENT_SUPPORT_REDIS_MEMORY_REJECT_RATIO"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
