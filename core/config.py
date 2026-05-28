from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

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
    database_admin_url: str = Field(default=LOCAL_ADMIN_DATABASE_URL)
    database_url: str = Field(default=LOCAL_APP_DATABASE_URL)
    redis_url: str = "redis://localhost:6379/0"
    qdrant_url: str = "http://localhost:6333"


@lru_cache
def get_settings() -> Settings:
    return Settings()
