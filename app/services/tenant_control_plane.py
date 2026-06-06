"""Tenant control-plane service layer."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant_context import set_local_tenant_context
from app.models.audit import AuditEvent
from app.models.service_principal import ServicePrincipal
from app.models.tenant import Tenant, TenantConfigVersion, TenantMembership
from app.schemas.service_principal import ServicePrincipalAuthResult
from app.schemas.tenant import ActorContext, TenantConfigUpdate, TenantCreate, TenantMemberCreate, TenantUpdate

ADMIN_ROLES = {"admin"}
WRITE_ROLES = {"admin", "moderator"}
ALLOWED_SERVICE_PRINCIPAL_SCOPES = {
    "tenant:read",
    "tenant:write",
    "config:read",
    "config:write",
    "source:read",
    "source:write",
    "capability:read",
    "capability:write",
}


class TenantControlPlaneError(ValueError):
    """Base tenant control-plane service error."""


class TenantNotFoundError(TenantControlPlaneError):
    """Tenant was not found."""


class TenantAccessDeniedError(TenantControlPlaneError):
    """Actor lacks tenant access."""


class TenantRuntimeDisabledError(TenantControlPlaneError):
    """Tenant is not active for runtime usage."""


class InvalidServicePrincipalError(TenantControlPlaneError):
    """Service principal credential is invalid."""


class TenantControlPlaneService:
    """Business logic for tenant control-plane operations."""

    def __init__(self, session: AsyncSession):
        """Create a service bound to a database session."""
        self.session = session

    async def create_tenant(self, payload: TenantCreate, actor: ActorContext) -> Tenant:
        """Create tenant with initial config version and audit event."""
        tenant = Tenant(
            slug=payload.slug,
            display_name=payload.display_name,
            retention_policy_json=payload.retention_policy_json,
            config_version=1,
        )
        self.session.add(tenant)
        await self.session.flush()
        await set_local_tenant_context(self.session, tenant.id)
        config = TenantConfigVersion(
            tenant_id=tenant.id,
            version=1,
            created_by_actor_type=actor.actor_type,
            created_by_actor_id=actor.actor_id,
            reason="initial_config",
        )
        self.session.add(config)
        await self.write_audit(
            tenant.id,
            actor,
            "tenant.create",
            before=None,
            after={"slug": tenant.slug, "display_name": tenant.display_name, "status": tenant.status},
        )
        await self.session.flush()
        return tenant

    async def get_tenant(self, tenant_id: UUID) -> Tenant:
        """Get a tenant or raise."""
        tenant = await self.session.get(Tenant, tenant_id)
        if tenant is None:
            raise TenantNotFoundError("Tenant not found")
        return tenant

    async def update_tenant(self, tenant_id: UUID, payload: TenantUpdate, actor: ActorContext) -> Tenant:
        """Update tenant metadata/status and audit the mutation."""
        tenant = await self.get_tenant(tenant_id)
        before = self._tenant_summary(tenant)
        if payload.display_name is not None:
            tenant.display_name = payload.display_name
        if payload.retention_policy_json is not None:
            tenant.retention_policy_json = payload.retention_policy_json
        if payload.status is not None:
            tenant.status = payload.status
            tenant.deleted_at = datetime.now(UTC) if payload.status == "deleting" else tenant.deleted_at
        await self.write_audit(
            tenant.id,
            actor,
            "tenant.update",
            before=before,
            after=self._tenant_summary(tenant),
            metadata={"reason": payload.reason} if payload.reason else {},
        )
        await self.session.flush()
        return tenant

    async def add_member(self, tenant_id: UUID, payload: TenantMemberCreate, actor: ActorContext) -> TenantMembership:
        """Add or update a tenant membership."""
        await self.get_tenant(tenant_id)
        result = await self.session.execute(
            select(TenantMembership).where(
                TenantMembership.tenant_id == tenant_id,
                TenantMembership.user_id == payload.user_id,
            )
        )
        membership = result.scalar_one_or_none()
        before = None
        if membership is None:
            membership = TenantMembership(tenant_id=tenant_id, user_id=payload.user_id, role=payload.role)
            self.session.add(membership)
        else:
            before = {"user_id": membership.user_id, "role": membership.role}
            membership.role = payload.role
        await self.write_audit(
            tenant_id,
            actor,
            "tenant.member.upsert",
            before=before,
            after={"user_id": payload.user_id, "role": payload.role},
        )
        await self.session.flush()
        return membership

    async def get_membership(self, tenant_id: UUID, user_id: int) -> TenantMembership | None:
        """Return a user's tenant membership when present."""
        result = await self.session.execute(
            select(TenantMembership).where(
                TenantMembership.tenant_id == tenant_id, TenantMembership.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    async def require_membership(self, tenant_id: UUID, user_id: int, allowed_roles: set[str]) -> TenantMembership:
        """Require membership with an allowed role."""
        membership = await self.get_membership(tenant_id, user_id)
        if membership is None or membership.role not in allowed_roles:
            raise TenantAccessDeniedError("Tenant role denied")
        return membership

    async def create_config_version(
        self,
        tenant_id: UUID,
        payload: TenantConfigUpdate,
        actor: ActorContext,
    ) -> TenantConfigVersion:
        """Create immutable config version and audit it."""
        tenant = await self.get_tenant(tenant_id)
        before = {"config_version": tenant.config_version}
        next_version = tenant.config_version + 1
        config = TenantConfigVersion(
            tenant_id=tenant_id,
            version=next_version,
            persona=payload.persona,
            official_links=payload.official_links,
            moderation_mode=payload.moderation_mode,
            model_budget=payload.model_budget,
            created_by_actor_type=actor.actor_type,
            created_by_actor_id=actor.actor_id,
            reason=payload.reason,
        )
        tenant.config_version = next_version
        self.session.add(config)
        await self.write_audit(
            tenant_id,
            actor,
            "tenant.config.update",
            before=before,
            after={"config_version": next_version, "moderation_mode": payload.moderation_mode},
            metadata={"reason": payload.reason} if payload.reason else {},
        )
        await self.session.flush()
        return config

    async def create_service_principal(
        self,
        tenant_id: UUID,
        name: str,
        scopes: list[str],
        actor: ActorContext,
        expires_at: datetime | None = None,
    ) -> tuple[ServicePrincipal, str]:
        """Create service principal and return the raw key once."""
        await self.ensure_tenant_active(tenant_id)
        unknown_scopes = set(scopes) - ALLOWED_SERVICE_PRINCIPAL_SCOPES
        if unknown_scopes:
            raise TenantControlPlaneError(f"Unknown scopes: {', '.join(sorted(unknown_scopes))}")
        raw_key = f"asp_{secrets.token_urlsafe(32)}"
        key_prefix = raw_key[:12]
        fingerprint = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:16]
        principal = ServicePrincipal(
            tenant_id=tenant_id,
            name=name,
            key_hash=self._hash_secret(raw_key),
            key_prefix=key_prefix,
            key_fingerprint=fingerprint,
            scopes=scopes,
            expires_at=expires_at,
        )
        self.session.add(principal)
        await self.write_audit(
            tenant_id,
            actor,
            "service_principal.create",
            before=None,
            after={"name": name, "scopes": scopes, "key_fingerprint": fingerprint},
        )
        await self.session.flush()
        return principal, raw_key

    async def revoke_service_principal(
        self, tenant_id: UUID, principal_id: UUID, actor: ActorContext
    ) -> ServicePrincipal:
        """Revoke a service principal."""
        principal = await self.session.get(ServicePrincipal, principal_id)
        if principal is None or principal.tenant_id != tenant_id:
            raise InvalidServicePrincipalError("Service principal not found")
        before = {"status": principal.status}
        principal.status = "revoked"
        principal.revoked_at = datetime.now(UTC)
        await self.write_audit(
            tenant_id,
            actor,
            "service_principal.revoke",
            before=before,
            after={"status": principal.status, "key_fingerprint": principal.key_fingerprint},
        )
        await self.session.flush()
        return principal

    async def authenticate_service_principal(
        self,
        api_key: str,
        tenant_id: UUID,
        required_scopes: set[str] | None = None,
    ) -> ServicePrincipalAuthResult:
        """Authenticate a raw service-principal key within a tenant RLS context."""
        key_prefix = api_key[:12]
        result = await self.session.execute(
            select(ServicePrincipal).where(
                ServicePrincipal.tenant_id == tenant_id, ServicePrincipal.key_prefix == key_prefix
            )
        )
        principal = result.scalar_one_or_none()
        now = datetime.now(UTC)
        if principal is None or not self._verify_secret(api_key, principal.key_hash):
            raise InvalidServicePrincipalError("Invalid service principal")
        if principal.status != "active" or principal.revoked_at is not None:
            raise InvalidServicePrincipalError("Service principal is not active")
        if principal.expires_at is not None and principal.expires_at <= now:
            raise InvalidServicePrincipalError("Service principal expired")
        if required_scopes and not required_scopes.issubset(set(principal.scopes)):
            raise TenantAccessDeniedError("Service principal scope denied")
        await self.ensure_tenant_active(principal.tenant_id)
        principal.last_used_at = now
        await self.session.flush()
        return ServicePrincipalAuthResult(
            id=principal.id,
            tenant_id=principal.tenant_id,
            scopes=principal.scopes,
            key_fingerprint=principal.key_fingerprint,
        )

    async def ensure_tenant_active(self, tenant_id: UUID) -> Tenant:
        """Require tenant active status for runtime/automation use."""
        tenant = await self.get_tenant(tenant_id)
        if tenant.status != "active":
            raise TenantRuntimeDisabledError("Tenant is not active")
        return tenant

    async def write_audit(
        self,
        tenant_id: UUID,
        actor: ActorContext,
        action: str,
        before: dict[str, Any] | None,
        after: dict[str, Any] | None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEvent:
        """Write a tenant-scoped audit event."""
        event = AuditEvent(
            tenant_id=tenant_id,
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
            action=action,
            before=before,
            after=after,
            metadata_json=metadata or {},
        )
        self.session.add(event)
        return event

    @staticmethod
    def _tenant_summary(tenant: Tenant) -> dict[str, Any]:
        return {
            "slug": tenant.slug,
            "display_name": tenant.display_name,
            "status": tenant.status,
            "config_version": tenant.config_version,
            "retention_policy_json": tenant.retention_policy_json,
        }

    @staticmethod
    def _hash_secret(secret: str) -> str:
        return bcrypt.hashpw(secret.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    @staticmethod
    def _verify_secret(secret: str, secret_hash: str) -> bool:
        return bcrypt.checkpw(secret.encode("utf-8"), secret_hash.encode("utf-8"))
