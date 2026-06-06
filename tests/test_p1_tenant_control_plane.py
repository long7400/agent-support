"""P1 tenant control-plane guardrail tests."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.schemas.tenant import ActorContext, TenantCreate, TenantUpdate
from app.services import tenant_control_plane
from app.services.tenant_control_plane import ALLOWED_SERVICE_PRINCIPAL_SCOPES, TenantControlPlaneService


class DummySession:
    """Minimal async session double for service tests that do not need a database."""

    def __init__(self) -> None:
        """Track added objects and flush calls."""
        self.added = []
        self.flushed = 0

    def add(self, obj: object) -> None:
        """Record an object that would be persisted."""
        self.added.append(obj)

    async def flush(self) -> None:
        """Record a flush boundary."""
        self.flushed += 1


def test_service_principal_key_is_hashed_and_returned_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """Create returns a raw key but stores only hash/prefix/fingerprint."""

    async def run() -> None:
        tenant_id = uuid4()
        session = DummySession()
        service = TenantControlPlaneService(session)  # type: ignore[arg-type]

        async def active_tenant(_tenant_id):
            return object()

        monkeypatch.setattr(service, "ensure_tenant_active", active_tenant)
        principal, raw_key = await service.create_service_principal(
            tenant_id,
            "ci",
            ["tenant:read"],
            ActorContext(actor_type="operator", actor_id="op"),
            datetime.now(UTC) + timedelta(days=1),
        )

        assert raw_key.startswith("asp_")
        assert principal.key_hash != raw_key
        assert principal.key_prefix == raw_key[:12]
        assert principal.key_fingerprint
        assert TenantControlPlaneService._verify_secret(raw_key, principal.key_hash)

    asyncio.run(run())


def test_create_tenant_writes_initial_config_and_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tenant creation creates the tenant, config v1, and audit event in one service call."""

    async def skip_db_context(_session, _tenant_id):
        return None

    monkeypatch.setattr(tenant_control_plane, "set_local_tenant_context", skip_db_context)

    async def run() -> None:
        session = DummySession()
        service = TenantControlPlaneService(session)  # type: ignore[arg-type]

        tenant = await service.create_tenant(
            TenantCreate(slug="acme", display_name="Acme"),
            ActorContext(actor_type="operator", actor_id="op"),
        )

        assert tenant.config_version == 1
        assert [obj.__class__.__name__ for obj in session.added] == ["Tenant", "TenantConfigVersion", "AuditEvent"]
        assert session.added[-1].action == "tenant.create"

    asyncio.run(run())


def test_tenant_update_schema_limits_status_values() -> None:
    """Lifecycle status is constrained to the P1 tenant states."""
    assert TenantUpdate(status="disabled").status == "disabled"
    with pytest.raises(ValueError):
        TenantUpdate(status="archived")


def test_allowed_service_principal_scopes_are_p1_scopes() -> None:
    """Initial automation scopes cover tenant/config/source/capability access."""
    assert {"tenant:read", "tenant:write", "config:write", "source:write", "capability:read"}.issubset(
        ALLOWED_SERVICE_PRINCIPAL_SCOPES
    )
