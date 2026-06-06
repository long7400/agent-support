"""Tenant control-plane persistence models."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.audit import AuditEvent
    from app.models.service_principal import ServicePrincipal

TENANT_STATUSES = ("active", "disabled", "suspended", "deleting")
TENANT_ROLES = ("admin", "moderator", "viewer")


class Tenant(TimestampMixin, Base):
    """Top-level tenant boundary."""

    __tablename__ = "tenants"
    __table_args__ = (
        CheckConstraint("status IN ('active','disabled','suspended','deleting')", name="ck_tenants_status"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    config_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    retention_policy_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)

    memberships: Mapped[list[TenantMembership]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    config_versions: Mapped[list[TenantConfigVersion]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )
    service_principals: Mapped[list[ServicePrincipal]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )
    audit_events: Mapped[list[AuditEvent]] = relationship(back_populates="tenant", cascade="all, delete-orphan")


class TenantRole(Base):
    """Reference role allowed for tenant memberships."""

    __tablename__ = "tenant_roles"

    name: Mapped[str] = mapped_column(String, primary_key=True)


class TenantMembership(TimestampMixin, Base):
    """Human user membership in a tenant."""

    __tablename__ = "tenant_memberships"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", name="uq_tenant_memberships_tenant_user"),
        CheckConstraint("role IN ('admin','moderator','viewer')", name="ck_tenant_memberships_role"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    role: Mapped[str] = mapped_column(String, ForeignKey("tenant_roles.name"), nullable=False)

    tenant: Mapped[Tenant] = relationship(back_populates="memberships")


class TenantConfigVersion(TimestampMixin, Base):
    """Immutable tenant config version."""

    __tablename__ = "tenant_config_versions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "version", name="uq_tenant_config_versions_tenant_version"),
        CheckConstraint(
            "moderation_mode IN ('shadow','propose','enforce')", name="ck_tenant_config_versions_moderation_mode"
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    persona: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    official_links: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    moderation_mode: Mapped[str] = mapped_column(String, nullable=False, default="shadow")
    model_budget: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_by_actor_type: Mapped[str] = mapped_column(String, nullable=False, default="operator")
    created_by_actor_id: Mapped[str] = mapped_column(String, nullable=False, default="system")
    reason: Mapped[str | None] = mapped_column(String, nullable=True)

    tenant: Mapped[Tenant] = relationship(back_populates="config_versions")
