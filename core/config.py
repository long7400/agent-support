from functools import lru_cache
from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LOCAL_ADMIN_TOKEN = "local-admin-token"
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
    database_admin_url: str = Field(default=LOCAL_ADMIN_DATABASE_URL)
    database_url: str = Field(default=LOCAL_APP_DATABASE_URL)
    redis_url: str = "redis://localhost:6379/0"
    qdrant_url: str = "http://localhost:6333"

    @model_validator(mode="after")
    def reject_default_admin_token_outside_local(self) -> Self:
        if (
            self.environment.casefold() in {"production", "prod", "staging"}
            and self.admin_token == LOCAL_ADMIN_TOKEN
        ):
            raise ValueError("AGENT_SUPPORT_ADMIN_TOKEN must be changed outside local env")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
