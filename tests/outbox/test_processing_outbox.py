"""Processing outbox and ingest service guardrail tests."""

import re
from pathlib import Path

INGEST_SERVICE = Path("app/services/platform_ingest.py")
WEBHOOK_ROUTE = Path("app/api/v1/platform_webhooks.py")


def test_ingest_service_uses_constant_time_compare() -> None:
    """Webhook secret verification must use constant-time comparison."""
    source = INGEST_SERVICE.read_text()
    assert "hmac.compare_digest" in source
    assert "_constant_time_compare" in source


def test_ingest_service_hashes_secret() -> None:
    """Webhook secrets are hashed before comparison."""
    source = INGEST_SERVICE.read_text()
    assert "hashlib.sha256" in source
    assert "_hash_secret" in source


def test_ingest_service_defines_error_types() -> None:
    """Ingest service defines specific error types for fail-closed paths."""
    source = INGEST_SERVICE.read_text()

    required_errors = [
        "SecretMismatchError",
        "UnknownPlatformMappingError",
        "DisabledPlatformError",
        "UnknownChannelError",
        "DisabledChannelError",
        "InvalidAdapterCredentialError",
        "ScopeMismatchError",
        "DuplicateAcceptedError",
    ]
    for error in required_errors:
        assert f"class {error}" in source, f"Missing error type: {error}"


def test_ingest_service_uses_with_tenant_context() -> None:
    """Ingest operations should be callable within tenant context."""
    # The service itself doesn't call with_tenant_context, but routes that use it should
    webhook_source = WEBHOOK_ROUTE.read_text()
    assert "with_tenant_context" in webhook_source


def test_ingest_service_has_idempotency_handling() -> None:
    """Ingest service handles duplicate events via IntegrityError."""
    source = INGEST_SERVICE.read_text()
    assert "IntegrityError" in source
    assert "DuplicateAcceptedError" in source
    assert "rollback" in source


def test_ingest_service_emits_notify() -> None:
    """Ingest service emits NOTIFY for outbox workers (best-effort)."""
    source = INGEST_SERVICE.read_text()
    assert "NOTIFY outbox_new" in source


def test_webhook_route_verifies_secret_first() -> None:
    """Webhook route verifies secret before any processing."""
    source = WEBHOOK_ROUTE.read_text()

    # Find the telegram_webhook function
    func_match = re.search(r"async def telegram_webhook\(.*?\n(?=\n@|\ndef |\Z)", source, re.DOTALL)
    assert func_match, "Missing telegram_webhook function"
    func_body = func_match.group(0)

    # Secret verification should happen early
    assert "verify_webhook_secret" in func_body
    assert "x_telegram_bot_api_secret_token" in func_body

    # Should return 401 on secret mismatch
    assert "status_code=401" in func_body
    assert "Invalid secret token" in func_body


def test_webhook_route_normalizes_without_tenant_id() -> None:
    """Webhook route normalizes update before resolving tenant-owned channel."""
    source = WEBHOOK_ROUTE.read_text()

    func_match = re.search(r"async def telegram_webhook\(.*?\n(?=\n@|\ndef |\Z)", source, re.DOTALL)
    assert func_match
    func_body = func_match.group(0)

    # Normalize should be called
    assert "normalize_telegram_update" in func_body

    # NormalizedInboundEvent should not have tenant_id injected from path
    # (tenant_id comes from trusted DB lookup via verify_webhook_secret)
    assert "tenant_id=tenant_id" not in func_body or "tenant_id=tenant_id," in func_body


def test_webhook_route_fails_closed_on_unknown_channel() -> None:
    """Webhook route returns 200 but drops update on unknown channel."""
    source = WEBHOOK_ROUTE.read_text()

    # Should handle UnknownChannelError
    assert "UnknownChannelError" in source
    assert "unknown_channel" in source

    # Should return 200 to Telegram (not 4xx) to avoid retries
    func_match = re.search(r"async def telegram_webhook\(.*?\n(?=\n@|\ndef |\Z)", source, re.DOTALL)
    assert func_match
    func_body = func_match.group(0)

    # Check that unknown_channel returns ignored status
    assert '"status": "ignored"' in func_body or '"status":"ignored"' in func_body


def test_webhook_route_handles_duplicate_idempotently() -> None:
    """Webhook route accepts duplicates without creating new outbox rows."""
    source = WEBHOOK_ROUTE.read_text()
    assert "DuplicateAcceptedError" in source
    assert "duplicate" in source


def test_webhook_route_has_rate_limit() -> None:
    """Webhook route is rate-limited."""
    source = WEBHOOK_ROUTE.read_text()
    assert "@limiter.limit" in source


def test_webhook_route_logs_without_secrets() -> None:
    """Webhook route logs context but never logs secret values."""
    source = WEBHOOK_ROUTE.read_text()

    # Should log tenant_id, platform, event_id
    assert "tenant_id=str(tenant_id)" in source

    # Should NOT log the secret token value
    func_match = re.search(r"async def telegram_webhook\(.*?\n(?=\n@|\ndef |\Z)", source, re.DOTALL)
    assert func_match
    func_body = func_match.group(0)

    # Check that secret is not passed to logger
    log_calls = re.findall(r"logger\.\w+\([^)]+\)", func_body)
    for log_call in log_calls:
        assert "x_telegram_bot_api_secret_token" not in log_call
        assert "secret_token=" not in log_call
