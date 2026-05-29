from uuid import uuid4

from core.services.audit import redact_audit_value
from core.services.principals import AdminPrincipal
from core.services.redaction import is_secret_like_key, secret_like_paths
from core.services.tenants import TenantService, UnsetValue


class FakeTenantRepository:
    def __init__(self) -> None:
        self.created: list[dict[str, object]] = []
        self.updated: list[dict[str, object]] = []

    def create(self, *, slug: str, display_name: str | None, config: dict[str, object]) -> object:
        tenant = {
            "id": uuid4(),
            "slug": slug,
            "display_name": display_name,
            "status": "active",
            "config": config,
            "config_version": 1,
        }
        self.created.append(tenant)
        return tenant

    def list(self) -> list[object]:
        return list(self.created)

    def get(self, tenant_id: object) -> object | None:
        for tenant in self.created:
            if tenant["id"] == tenant_id:
                return tenant
        return None

    def update_config(
        self,
        *,
        tenant_id: object,
        display_name: str | None | UnsetValue,
        config: dict[str, object] | UnsetValue,
    ) -> tuple[dict[str, object], dict[str, object] | None]:
        if isinstance(display_name, UnsetValue) or isinstance(config, UnsetValue):
            return {}, None
        before = {
            "id": tenant_id,
            "slug": "tenant-a",
            "display_name": "before",
            "status": "active",
            "config": {"persona": "old"},
            "config_version": 1,
        }
        after = before | {
            "display_name": display_name,
            "config": config,
            "config_version": 2,
        }
        self.updated.append(after)
        return before, after


class FakePluginRepository:
    def __init__(self) -> None:
        self.enabled: list[dict[str, object]] = []
        self.disabled: list[dict[str, object]] = []

    def upsert_enabled(
        self,
        *,
        tenant_id: object,
        plugin_name: str,
        config: dict[str, object],
    ) -> tuple[dict[str, object] | None, dict[str, object]]:
        after = {
            "id": uuid4(),
            "tenant_id": tenant_id,
            "plugin_name": plugin_name,
            "enabled": True,
            "config": config,
        }
        self.enabled.append(after)
        return None, after

    def disable(
        self,
        *,
        tenant_id: object,
        plugin_name: str,
    ) -> tuple[dict[str, object], dict[str, object]]:
        before = {
            "id": uuid4(),
            "tenant_id": tenant_id,
            "plugin_name": plugin_name,
            "enabled": True,
            "config": {},
        }
        after = before | {"enabled": False}
        self.disabled.append(after)
        return before, after


class FakeAuditService:
    def __init__(self) -> None:
        self.actions: list[str] = []

    def record(
        self,
        *,
        tenant_id: object | None,
        trace_id: object,
        principal: AdminPrincipal,
        action: str,
        resource_type: str,
        resource_id: str,
        before: object | None,
        after: object | None,
    ) -> None:
        del tenant_id, trace_id, principal, resource_type, resource_id, before, after
        self.actions.append(action)


def test_tenant_service_records_audit_for_create_and_plugin_enable() -> None:
    tenant_repo = FakeTenantRepository()
    plugin_repo = FakePluginRepository()
    audit = FakeAuditService()
    service = TenantService(tenant_repo, plugin_repo, audit)
    principal = AdminPrincipal(actor_type="admin_token", actor_id="local-admin")
    trace_id = uuid4()

    tenant = service.create_tenant(
        slug="tenant-a",
        display_name="Tenant A",
        config={"persona": "friendly"},
        principal=principal,
        trace_id=trace_id,
    )
    service.enable_plugin(
        tenant_id=tenant["id"],
        plugin_name="rag.search",
        config={},
        principal=principal,
        trace_id=trace_id,
    )

    assert audit.actions == ["tenant.created", "tenant_plugin.enabled"]


def test_redact_audit_value_hides_secret_like_keys() -> None:
    value = {
        "safe": "visible",
        "api_token": "hidden",
        "nested": {"password": "hidden"},  # pragma: allowlist secret
    }

    assert redact_audit_value(value) == {
        "safe": "visible",
        "api_token": "[REDACTED]",
        "nested": {"password": "[REDACTED]"},
    }


def test_secret_like_paths_reports_nested_credential_keys() -> None:
    value = {
        "safe": "visible",
        "nested": [
            {"api_key": "hidden"},  # pragma: allowlist secret
            {"config": {"token": "hidden"}},
        ],
    }

    assert secret_like_paths(value) == ["nested[0].api_key", "nested[1].config.token"]


def test_secret_like_key_detection_catches_separator_and_case_bypass() -> None:
    assert is_secret_like_key("api-key")  # pragma: allowlist secret
    assert is_secret_like_key("accessKey")
    assert is_secret_like_key("private_key")  # pragma: allowlist secret
    assert is_secret_like_key("authorization")
    assert is_secret_like_key("to\u200bken")
    assert is_secret_like_key("t\u043eken")
    assert not is_secret_like_key("top_k")


def test_secret_like_paths_reports_header_value_smuggling() -> None:
    value = {
        "headers": ["Authorization: Bearer demo-placeholder"],
        "safe": "visible",
    }

    assert secret_like_paths(value) == ["headers[0]"]
