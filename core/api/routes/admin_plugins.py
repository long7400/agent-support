from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path

from core.api.dependencies import get_trace_id, require_admin_principal
from core.api.routes.admin_tenants import get_tenant_service
from core.api.schemas.plugins import (
    TenantPluginResponse,
    TenantPluginUpdateRequest,
    tenant_plugin_response,
)
from core.services.principals import AdminPrincipal
from core.services.tenants import TenantService

router = APIRouter(prefix="/admin/tenants/{tenant_id}/plugins", tags=["admin-plugins"])

AdminDep = Annotated[AdminPrincipal, Depends(require_admin_principal)]
TraceDep = Annotated[UUID, Depends(get_trace_id)]
TenantServiceDep = Annotated[TenantService, Depends(get_tenant_service)]
PluginNamePath = Annotated[
    str,
    Path(min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9_.-]*$"),
]


@router.put("/{plugin_name}", response_model=TenantPluginResponse)
def enable_plugin(
    tenant_id: UUID,
    plugin_name: PluginNamePath,
    request: TenantPluginUpdateRequest,
    principal: AdminDep,
    trace_id: TraceDep,
    service: TenantServiceDep,
) -> TenantPluginResponse:
    plugin = service.enable_plugin(
        tenant_id=tenant_id,
        plugin_name=plugin_name,
        config=request.config,
        principal=principal,
        trace_id=trace_id,
    )
    return tenant_plugin_response(plugin)


@router.delete("/{plugin_name}", response_model=TenantPluginResponse)
def disable_plugin(
    tenant_id: UUID,
    plugin_name: PluginNamePath,
    principal: AdminDep,
    trace_id: TraceDep,
    service: TenantServiceDep,
) -> TenantPluginResponse:
    plugin = service.disable_plugin(
        tenant_id=tenant_id,
        plugin_name=plugin_name,
        principal=principal,
        trace_id=trace_id,
    )
    return tenant_plugin_response(plugin)
