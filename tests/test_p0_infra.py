"""P0 infrastructure guardrail tests."""

import asyncio

import pytest
from dotenv import dotenv_values

from app.core import observability
from app.core.config import (
    Environment,
    settings,
)
from app.core.database import build_async_database_url
from app.core.kms import (
    KMSConfigurationError,
    LocalKMSProvider,
    validate_kms_configuration,
)
from app.core.runtime_guardrails import (
    RuntimeGuardrailError,
    validate_runtime_guardrails,
)
from app.models import database as _database_models  # noqa: F401
from app.models.base import Base
from app.services.memory import MemoryService


def test_env_example_uses_host_run_service_defaults() -> None:
    """Environment template keeps host-run processes off Docker-only DNS names."""
    values = dotenv_values(".env.example")

    assert values["VALKEY_HOST"] == ""
    assert values["QDRANT_URL"] == "http://localhost:6333"
    assert values["LANGFUSE_HOST"] == "http://localhost:3001"
    assert values["LANGFUSE_CONTAINER_HOST"] == "http://langfuse-web:3000"


def test_local_kms_round_trip() -> None:
    """Local KMS provider encrypts and decrypts development handles."""
    provider = LocalKMSProvider(secret="test-secret")
    handle = asyncio.run(provider.encrypt(b"telegram-token"))

    assert handle.startswith("local:v1:")
    assert asyncio.run(provider.decrypt(handle)) == b"telegram-token"


def test_local_kms_rejects_tampered_handle() -> None:
    """Local KMS provider authenticates handles before decrypting."""
    provider = LocalKMSProvider(secret="test-secret")
    handle = asyncio.run(provider.encrypt(b"telegram-token"))
    tampered = handle[:-2] + "aa"

    with pytest.raises(KMSConfigurationError):
        asyncio.run(provider.decrypt(tampered))


def test_production_rejects_local_kms(monkeypatch: pytest.MonkeyPatch) -> None:
    """Production startup fails closed when local KMS is configured."""
    monkeypatch.setattr(settings, "ENVIRONMENT", Environment.PRODUCTION)
    monkeypatch.setattr(settings, "KMS_PROVIDER", "local")

    with pytest.raises(KMSConfigurationError):
        validate_kms_configuration()


def test_production_rejects_placeholder_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    """Production startup rejects placeholder credentials even with cloud KMS."""
    monkeypatch.setattr(settings, "ENVIRONMENT", Environment.PRODUCTION)
    monkeypatch.setattr(settings, "KMS_PROVIDER", "gcp")
    monkeypatch.setattr(settings, "GCP_KMS_KEY_NAME", "projects/example/locations/global/keyRings/dev/cryptoKeys/app")
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", "replace-with-a-long-random-value")
    monkeypatch.setattr(settings, "POSTGRES_PASSWORD", "agent_support_dev_password")
    monkeypatch.setattr(settings, "ALLOWED_ORIGINS", ["https://app.example.invalid"])
    monkeypatch.setattr(settings, "REQUIRE_OPENAI_API_KEY", False)
    monkeypatch.setattr(settings, "LANGFUSE_TRACING_ENABLED", False)

    with pytest.raises(RuntimeGuardrailError):
        validate_runtime_guardrails()


def test_production_rejects_disabled_langfuse_tracing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Production startup requires Langfuse tracing instead of silently running untraced LLM calls."""
    monkeypatch.setattr(settings, "ENVIRONMENT", Environment.PRODUCTION)
    monkeypatch.setattr(settings, "KMS_PROVIDER", "gcp")
    monkeypatch.setattr(settings, "GCP_KMS_KEY_NAME", "projects/example/locations/global/keyRings/prod/cryptoKeys/app")
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", "production-jwt-secret-with-enough-length")
    monkeypatch.setattr(settings, "POSTGRES_PASSWORD", "production-postgres-password")
    monkeypatch.setattr(settings, "ALLOWED_ORIGINS", ["https://app.example.invalid"])
    monkeypatch.setattr(settings, "REQUIRE_OPENAI_API_KEY", True)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-test-openai-key")
    monkeypatch.setattr(settings, "LANGFUSE_TRACING_ENABLED", False)
    monkeypatch.setattr(settings, "LANGFUSE_PUBLIC_KEY", "")
    monkeypatch.setattr(settings, "LANGFUSE_SECRET_KEY", "")

    with pytest.raises(RuntimeGuardrailError):
        validate_runtime_guardrails()


def test_langfuse_disabled_does_not_auth_check(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disabled Langfuse tracing does not call the network auth check."""

    class FailIfConstructed:
        def __init__(self, *args: object, **kwargs: object) -> None:
            raise AssertionError("langfuse client should not be constructed")

    monkeypatch.setattr(settings, "LANGFUSE_TRACING_ENABLED", False)
    monkeypatch.setattr(observability, "Langfuse", FailIfConstructed)

    observability.langfuse_init()


def test_memory_service_disabled_is_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    """Long-term memory stays disabled by default for community mode."""
    monkeypatch.setattr(settings, "LONG_TERM_MEMORY_ENABLED", False)
    monkeypatch.setattr(settings, "LONG_TERM_MEMORY_WRITE_ENABLED", False)
    service = MemoryService()

    assert asyncio.run(service.search("user-1", "hello")) == ""
    asyncio.run(service.add("user-1", [{"role": "user", "content": "hello"}]))
    assert service._memory is None


def test_sqlalchemy_metadata_registered() -> None:
    """P0 ORM migration exposes SQLAlchemy metadata for Alembic."""
    assert {"user", "session", "thread"}.issubset(Base.metadata.tables.keys())


def test_async_database_url_uses_asyncpg() -> None:
    """Runtime database sessions use an async PostgreSQL driver."""
    assert build_async_database_url().startswith("postgresql+asyncpg://")
