from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from core.api.dependencies import (
    get_admin_session,
    get_trace_id,
    require_admin_principal,
)
from core.api.schemas.tenants import TenantCreateRequest, TenantResponse, TenantUpdateRequest
from core.services.principals import AdminPrincipal
from core.services.tenants import UNSET, JsonObject, TenantService, UnsetValue

router = APIRouter(prefix="/admin/tenants", tags=["admin-tenants"])

AdminDep = Annotated[AdminPrincipal, Depends(require_admin_principal)]
SessionDep = Annotated[Session, Depends(get_admin_session)]
TraceDep = Annotated[UUID, Depends(get_trace_id)]


def get_tenant_service(
    principal: AdminDep,
    session: SessionDep,
) -> TenantService:
    del principal
    return TenantService.from_session(session)


TenantServiceDep = Annotated[TenantService, Depends(get_tenant_service)]


@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
def create_tenant(
    request: TenantCreateRequest,
    principal: AdminDep,
    trace_id: TraceDep,
    service: TenantServiceDep,
) -> TenantResponse:
    tenant = service.create_tenant(
        slug=request.slug,
        display_name=request.display_name,
        config=request.config.model_dump(exclude_none=True),
        principal=principal,
        trace_id=trace_id,
    )
    return TenantResponse.model_validate(tenant)


@router.get("", response_model=list[TenantResponse])
def list_tenants(
    principal: AdminDep,
    service: TenantServiceDep,
) -> list[TenantResponse]:
    del principal
    return [TenantResponse.model_validate(tenant) for tenant in service.list_tenants()]


@router.get("/{tenant_id}", response_model=TenantResponse)
def get_tenant(
    tenant_id: UUID,
    principal: AdminDep,
    service: TenantServiceDep,
) -> TenantResponse:
    del principal
    return TenantResponse.model_validate(service.get_tenant(tenant_id))


@router.patch("/{tenant_id}", response_model=TenantResponse)
def update_tenant(
    tenant_id: UUID,
    request: TenantUpdateRequest,
    principal: AdminDep,
    trace_id: TraceDep,
    service: TenantServiceDep,
) -> TenantResponse:
    display_name: str | None | UnsetValue = (
        request.display_name if "display_name" in request.model_fields_set else UNSET
    )
    config: JsonObject | UnsetValue = UNSET
    if "config" in request.model_fields_set:
        config = request.config.model_dump(exclude_none=True) if request.config is not None else {}

    tenant = service.update_tenant(
        tenant_id=tenant_id,
        display_name=display_name,
        config=config,
        principal=principal,
        trace_id=trace_id,
    )
    return TenantResponse.model_validate(tenant)
