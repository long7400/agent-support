from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from core.persistence.models import Tenant, TenantPlugin
from core.persistence.repositories.audit_log import AuditLogRepository
from core.persistence.repositories.tenant_plugins import TenantPluginRepository, plugin_snapshot
from core.persistence.repositories.tenants import (
    UNSET,
    TenantRepository,
    UnsetValue,
    tenant_snapshot,
)
from core.services.audit import AuditService
from core.services.errors import ServiceError
from core.services.principals import AdminPrincipal

JsonObject = dict[str, Any]

__all__ = ["JsonObject", "TenantService", "UNSET", "UnsetValue"]


class TenantRepositoryProtocol(Protocol):
    def create(self, *, slug: str, display_name: str | None, config: JsonObject) -> Any: ...

    def list(self) -> list[Any]: ...

    def get(self, tenant_id: UUID) -> Any | None: ...

    def update_config(
        self,
        *,
        tenant_id: UUID,
        display_name: str | None | UnsetValue,
        config: JsonObject | UnsetValue,
    ) -> tuple[JsonObject, Any | None]: ...


class TenantPluginRepositoryProtocol(Protocol):
    def upsert_enabled(
        self,
        *,
        tenant_id: UUID,
        plugin_name: str,
        config: JsonObject,
    ) -> tuple[JsonObject | None, Any]: ...

    def disable(self, *, tenant_id: UUID, plugin_name: str) -> tuple[JsonObject, Any | None]: ...


class AuditServiceProtocol(Protocol):
    def record(
        self,
        *,
        tenant_id: UUID | None,
        trace_id: UUID,
        principal: AdminPrincipal,
        action: str,
        resource_type: str,
        resource_id: str,
        before: object | None,
        after: object | None,
    ) -> None: ...


def snapshot_resource(resource: Any) -> JsonObject:
    if isinstance(resource, Tenant):
        return tenant_snapshot(resource)
    if isinstance(resource, TenantPlugin):
        return plugin_snapshot(resource)
    if isinstance(resource, dict):
        return resource
    return {"id": str(getattr(resource, "id", ""))}


def resource_id(resource: Any) -> UUID:
    if isinstance(resource, dict):
        value = resource["id"]
        if isinstance(value, UUID):
            return value
    value = resource.id
    if isinstance(value, UUID):
        return value
    raise TypeError("resource id must be a UUID")


class TenantService:
    def __init__(
        self,
        tenant_repository: TenantRepositoryProtocol,
        plugin_repository: TenantPluginRepositoryProtocol,
        audit_service: AuditServiceProtocol,
    ) -> None:
        self.tenants = tenant_repository
        self.plugins = plugin_repository
        self.audit = audit_service

    @classmethod
    def from_session(cls, session: Any) -> TenantService:
        audit = AuditService(repository=AuditLogRepository(session))
        return cls(
            tenant_repository=TenantRepository(session),
            plugin_repository=TenantPluginRepository(session),
            audit_service=audit,
        )

    def create_tenant(
        self,
        *,
        slug: str,
        display_name: str | None,
        config: JsonObject,
        principal: AdminPrincipal,
        trace_id: UUID,
    ) -> Any:
        try:
            tenant = self.tenants.create(slug=slug, display_name=display_name, config=config)
        except IntegrityError as exc:
            raise ServiceError(
                code="TENANT_CONFLICT",
                message="Tenant slug already exists",
                status_code=409,
            ) from exc
        tenant_id = resource_id(tenant)
        self.audit.record(
            tenant_id=tenant_id,
            trace_id=trace_id,
            principal=principal,
            action="tenant.created",
            resource_type="tenant",
            resource_id=str(tenant_id),
            before=None,
            after=snapshot_resource(tenant),
        )
        return tenant

    def list_tenants(self) -> list[Any]:
        return self.tenants.list()

    def get_tenant(self, tenant_id: UUID) -> Any:
        tenant = self.tenants.get(tenant_id)
        if tenant is None:
            raise ServiceError(code="TENANT_NOT_FOUND", message="Tenant not found", status_code=404)
        return tenant

    def update_tenant(
        self,
        *,
        tenant_id: UUID,
        display_name: str | None | UnsetValue,
        config: JsonObject | UnsetValue,
        principal: AdminPrincipal,
        trace_id: UUID,
    ) -> Any:
        before, tenant = self.tenants.update_config(
            tenant_id=tenant_id,
            display_name=display_name,
            config=config,
        )
        if tenant is None:
            raise ServiceError(code="TENANT_NOT_FOUND", message="Tenant not found", status_code=404)
        self.audit.record(
            tenant_id=tenant_id,
            trace_id=trace_id,
            principal=principal,
            action="tenant.updated",
            resource_type="tenant",
            resource_id=str(tenant_id),
            before=before,
            after=snapshot_resource(tenant),
        )
        return tenant

    def enable_plugin(
        self,
        *,
        tenant_id: UUID,
        plugin_name: str,
        config: JsonObject,
        principal: AdminPrincipal,
        trace_id: UUID,
    ) -> Any:
        if self.tenants.get(tenant_id) is None:
            raise ServiceError(code="TENANT_NOT_FOUND", message="Tenant not found", status_code=404)
        before, plugin = self.plugins.upsert_enabled(
            tenant_id=tenant_id,
            plugin_name=plugin_name,
            config=config,
        )
        self.audit.record(
            tenant_id=tenant_id,
            trace_id=trace_id,
            principal=principal,
            action="tenant_plugin.enabled",
            resource_type="tenant_plugin",
            resource_id=f"{tenant_id}:{plugin_name}",
            before=before,
            after=snapshot_resource(plugin),
        )
        return plugin

    def disable_plugin(
        self,
        *,
        tenant_id: UUID,
        plugin_name: str,
        principal: AdminPrincipal,
        trace_id: UUID,
    ) -> Any:
        if self.tenants.get(tenant_id) is None:
            raise ServiceError(code="TENANT_NOT_FOUND", message="Tenant not found", status_code=404)
        before, plugin = self.plugins.disable(tenant_id=tenant_id, plugin_name=plugin_name)
        if plugin is None:
            raise ServiceError(code="PLUGIN_NOT_FOUND", message="Plugin not found", status_code=404)
        self.audit.record(
            tenant_id=tenant_id,
            trace_id=trace_id,
            principal=principal,
            action="tenant_plugin.disabled",
            resource_type="tenant_plugin",
            resource_id=f"{tenant_id}:{plugin_name}",
            before=before,
            after=snapshot_resource(plugin),
        )
        return plugin
