"""Adapter ingest API guardrail tests."""

import re
from pathlib import Path

ADAPTER_INGEST_ROUTE = Path("app/api/v1/adapter_ingest.py")
ADAPTER_SCHEMA = Path("app/schemas/adapter.py")


def test_adapter_ingest_requires_credential_header() -> None:
    """Adapter ingest requires X-Adapter-Credential header."""
    source = ADAPTER_INGEST_ROUTE.read_text()
    assert "x_adapter_credential" in source.lower() or "X-Adapter-Credential" in source
    assert "require_adapter_principal" in source


def test_adapter_ingest_has_separate_auth_dependency() -> None:
    """Adapter ingest uses its own auth dependency, not human JWT auth."""
    source = ADAPTER_INGEST_ROUTE.read_text()

    # Should have its own auth function
    assert "async def require_adapter_principal" in source

    # Should NOT use get_current_user or require_tenant_admin
    assert "get_current_user" not in source
    assert "require_tenant_admin" not in source
    assert "authenticate_service_principal" not in source


def test_adapter_ingest_validates_normalized_event_schema() -> None:
    """Adapter ingest accepts NormalizedInboundEvent as body."""
    source = ADAPTER_INGEST_ROUTE.read_text()
    assert "NormalizedInboundEvent" in source


def test_normalized_inbound_event_forbids_tenant_id() -> None:
    """NormalizedInboundEvent schema must forbid tenant_id field."""
    source = ADAPTER_SCHEMA.read_text()

    # Find the NormalizedInboundEvent class
    class_match = re.search(r"class NormalizedInboundEvent.*?(?=\nclass |\Z)", source, re.DOTALL)
    assert class_match, "Missing NormalizedInboundEvent class"
    class_body = class_match.group(0)

    # Must have extra="forbid"
    assert 'extra="forbid"' in class_body or "extra='forbid'" in class_body

    # Must NOT have tenant_id field
    assert "tenant_id:" not in class_body
    assert "tenant_id =" not in class_body


def test_adapter_ingest_checks_platform_scope() -> None:
    """Adapter ingest validates principal platform matches body platform."""
    source = ADAPTER_INGEST_ROUTE.read_text()

    func_match = re.search(r"async def adapter_ingest\(.*?\n(?=\n@|\ndef |\Z)", source, re.DOTALL)
    assert func_match
    func_body = func_match.group(0)

    assert "principal.platform" in func_body
    assert "body.platform" in func_body


def test_adapter_ingest_checks_channel_scope() -> None:
    """Adapter ingest validates channel is allowed by principal scope."""
    source = ADAPTER_INGEST_ROUTE.read_text()

    func_match = re.search(r"async def adapter_ingest\(.*?\n(?=\n@|\ndef |\Z)", source, re.DOTALL)
    assert func_match
    func_body = func_match.group(0)

    assert "is_channel_allowed" in func_body


def test_adapter_ingest_uses_tenant_context() -> None:
    """Adapter ingest operations run under tenant RLS context."""
    source = ADAPTER_INGEST_ROUTE.read_text()
    assert "with_tenant_context" in source


def test_adapter_ingest_handles_duplicate() -> None:
    """Adapter ingest accepts duplicates idempotently."""
    source = ADAPTER_INGEST_ROUTE.read_text()
    assert "DuplicateAcceptedError" in source


def test_adapter_ingest_has_rate_limit() -> None:
    """Adapter ingest route is rate-limited."""
    source = ADAPTER_INGEST_ROUTE.read_text()
    assert "@limiter.limit" in source


def test_adapter_ingest_logs_without_credential_secret() -> None:
    """Adapter ingest logs context but never logs credential secret values."""
    source = ADAPTER_INGEST_ROUTE.read_text()

    # Should log tenant_id, platform
    assert "tenant_id=str(tenant_id)" in source

    # Find log calls and verify no credential secrets
    log_calls = re.findall(r"logger\.\w+\([^)]+\)", source)
    for log_call in log_calls:
        assert "x_adapter_credential" not in log_call
        assert "credential_raw" not in log_call


def test_adapter_credential_resolution_uses_prefix_lookup() -> None:
    """Adapter credential lookup uses prefix for efficient DB query."""
    ingest_service = Path("app/services/platform_ingest.py").read_text()

    func_match = re.search(
        r"async def resolve_adapter_credential\(.*?\n(?=\nasync def|\ndef |\Z)", ingest_service, re.DOTALL
    )
    assert func_match
    func_body = func_match.group(0)

    assert "credential_prefix" in func_body
    assert "credential_hash" in func_body


def test_adapter_credential_resolution_verifies_status() -> None:
    """Adapter credential resolution verifies status is active."""
    ingest_service = Path("app/services/platform_ingest.py").read_text()

    func_match = re.search(
        r"async def resolve_adapter_credential\(.*?\n(?=\nasync def|\ndef |\Z)", ingest_service, re.DOTALL
    )
    assert func_match
    func_body = func_match.group(0)

    assert "status" in func_body
    assert "active" in func_body


def test_adapter_credential_resolution_checks_expiry() -> None:
    """Adapter credential resolution checks expires_at."""
    ingest_service = Path("app/services/platform_ingest.py").read_text()

    func_match = re.search(
        r"async def resolve_adapter_credential\(.*?\n(?=\nasync def|\ndef |\Z)", ingest_service, re.DOTALL
    )
    assert func_match
    func_body = func_match.group(0)

    assert "expires_at" in func_body
