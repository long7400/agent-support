"""Tenant admin/operator API routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.v1.auth import require_operator, require_tenant_admin
from app.infra.config import settings
from app.infra.database import AsyncSessionLocal
from app.infra.limiter import limiter
from app.infra.tenant_context import with_tenant_context
from app.schemas.service_principal import (
    ServicePrincipalCreate,
    ServicePrincipalCreateResponse,
    ServicePrincipalResponse,
)
from app.schemas.tenant import (
    ActorContext,
    TenantConfigUpdate,
    TenantConfigVersionResponse,
    TenantCreate,
    TenantMemberCreate,
    TenantMembershipResponse,
    TenantResponse,
    TenantUpdate,
)
from app.services.tenant_control_plane import (
    InvalidServicePrincipalError,
    TenantAccessDeniedError,
    TenantControlPlaneError,
    TenantControlPlaneService,
    TenantNotFoundError,
    TenantRuntimeDisabledError,
)

router = APIRouter()


def tenant_control_plane_http_error(exc: TenantControlPlaneError) -> HTTPException:
    """Map service-layer tenant errors to stable API responses."""
    if isinstance(exc, (TenantNotFoundError, InvalidServicePrincipalError)):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, TenantAccessDeniedError):
        return HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, TenantRuntimeDisabledError):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


@router.post("", response_model=TenantResponse)
@limiter.limit(settings.RATE_LIMIT_DEFAULT[0])
async def create_tenant(request: Request, payload: TenantCreate, actor: ActorContext = Depends(require_operator)):
    """Create a tenant. Operator-only for P1."""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            tenant = await TenantControlPlaneService(session).create_tenant(payload, actor)
            response = TenantResponse.model_validate(tenant)
        return response


@router.get("/{tenant_id}", response_model=TenantResponse)
@limiter.limit(settings.RATE_LIMIT_DEFAULT[0])
async def get_tenant(request: Request, tenant_id: UUID, actor: ActorContext = Depends(require_tenant_admin)):
    """Read tenant metadata for tenant admins."""
    async with AsyncSessionLocal() as session:
        async with with_tenant_context(session, tenant_id):
            try:
                tenant = await TenantControlPlaneService(session).get_tenant(tenant_id)
            except TenantControlPlaneError as exc:
                raise tenant_control_plane_http_error(exc) from exc
            response = TenantResponse.model_validate(tenant)
        return response


@router.patch("/{tenant_id}", response_model=TenantResponse)
@limiter.limit(settings.RATE_LIMIT_DEFAULT[0])
async def update_tenant(
    request: Request, tenant_id: UUID, payload: TenantUpdate, actor: ActorContext = Depends(require_operator)
):
    """Update tenant metadata/status. Operator-only for lifecycle status."""
    async with AsyncSessionLocal() as session:
        async with with_tenant_context(session, tenant_id):
            try:
                tenant = await TenantControlPlaneService(session).update_tenant(tenant_id, payload, actor)
            except TenantControlPlaneError as exc:
                raise tenant_control_plane_http_error(exc) from exc
            response = TenantResponse.model_validate(tenant)
        return response


@router.post("/{tenant_id}/members", response_model=TenantMembershipResponse)
@limiter.limit(settings.RATE_LIMIT_DEFAULT[0])
async def add_member(
    request: Request, tenant_id: UUID, payload: TenantMemberCreate, actor: ActorContext = Depends(require_operator)
):
    """Add or update tenant membership."""
    async with AsyncSessionLocal() as session:
        async with with_tenant_context(session, tenant_id):
            try:
                membership = await TenantControlPlaneService(session).add_member(tenant_id, payload, actor)
            except TenantControlPlaneError as exc:
                raise tenant_control_plane_http_error(exc) from exc
            response = TenantMembershipResponse.model_validate(membership)
        return response


@router.post("/{tenant_id}/config", response_model=TenantConfigVersionResponse)
@limiter.limit(settings.RATE_LIMIT_DEFAULT[0])
async def update_config(
    request: Request, tenant_id: UUID, payload: TenantConfigUpdate, actor: ActorContext = Depends(require_tenant_admin)
):
    """Create a new immutable tenant config version."""
    async with AsyncSessionLocal() as session:
        async with with_tenant_context(session, tenant_id):
            try:
                config = await TenantControlPlaneService(session).create_config_version(tenant_id, payload, actor)
            except TenantControlPlaneError as exc:
                raise tenant_control_plane_http_error(exc) from exc
            response = TenantConfigVersionResponse.model_validate(config)
        return response


@router.post("/{tenant_id}/service-principals", response_model=ServicePrincipalCreateResponse)
@limiter.limit(settings.RATE_LIMIT_DEFAULT[0])
async def create_service_principal(
    request: Request,
    tenant_id: UUID,
    payload: ServicePrincipalCreate,
    actor: ActorContext = Depends(require_tenant_admin),
):
    """Create a tenant service principal and return its raw key once."""
    async with AsyncSessionLocal() as session:
        async with with_tenant_context(session, tenant_id):
            service = TenantControlPlaneService(session)
            try:
                principal, raw_key = await service.create_service_principal(
                    tenant_id,
                    payload.name,
                    payload.scopes,
                    actor,
                    payload.expires_at,
                )
            except TenantControlPlaneError as exc:
                raise tenant_control_plane_http_error(exc) from exc
            response = ServicePrincipalCreateResponse(
                **ServicePrincipalResponse.model_validate(principal).model_dump(),
                api_key=raw_key,
            )
        return response


@router.post("/{tenant_id}/service-principals/{principal_id}/revoke", response_model=ServicePrincipalResponse)
@limiter.limit(settings.RATE_LIMIT_DEFAULT[0])
async def revoke_service_principal(
    request: Request,
    tenant_id: UUID,
    principal_id: UUID,
    actor: ActorContext = Depends(require_tenant_admin),
):
    """Revoke a tenant service principal."""
    async with AsyncSessionLocal() as session:
        async with with_tenant_context(session, tenant_id):
            try:
                principal = await TenantControlPlaneService(session).revoke_service_principal(
                    tenant_id, principal_id, actor
                )
            except TenantControlPlaneError as exc:
                raise tenant_control_plane_http_error(exc) from exc
            response = ServicePrincipalResponse.model_validate(principal)
        return response
