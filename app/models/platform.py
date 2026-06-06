"""Platform integration persistence models."""

from __future__ import annotations

from datetime import datetime, UTC
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

PLATFORM_TYPES = ("telegram", "discord")
PLATFORM_STATUSES = ("active", "disabled", "suspended")
CREDENTIAL_STATUSES = ("active", "revoked", "expired")
CHANNEL_STATUSES = ("active", "disabled", "archived")


class TenantPlatform(TimestampMixin, Base):
    """Tenant's platform integration (Telegram, Discord, etc.)."""

    __tablename__ = "tenant_platforms"
    __table_args__ = (
        CheckConstraint("platform IN ('telegram','discord')", name="ck_tenant_platforms_platform"),
        CheckConstraint("status IN ('active','disabled','suspended')", name="ck_tenant_platforms_status"),
        UniqueConstraint(
            "tenant_id", "platform", "external_workspace_id", name="uq_tenant_platforms_tenant_platform_workspace"
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String, nullable=False)
    external_workspace_id: Mapped[str | None] = mapped_column(String, nullable=True)
    webhook_secret_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    config_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    channels: Mapped[list[PlatformChannel]] = relationship(
        back_populates="tenant_platform", cascade="all, delete-orphan"
    )


class AdapterCredential(TimestampMixin, Base):
    """Credentials for adapter principal authentication."""

    __tablename__ = "adapter_credentials"
    __table_args__ = (
        CheckConstraint("platform IN ('telegram','discord')", name="ck_adapter_credentials_platform"),
        CheckConstraint("status IN ('active','revoked','expired')", name="ck_adapter_credentials_status"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    credential_hash: Mapped[str] = mapped_column(String, nullable=False)
    credential_prefix: Mapped[str] = mapped_column(String, nullable=False)
    credential_fingerprint: Mapped[str] = mapped_column(String, nullable=False)
    allowed_channel_patterns: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    scopes: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PlatformChannel(TimestampMixin, Base):
    """Channel/thread within a platform."""

    __tablename__ = "platform_channels"
    __table_args__ = (
        CheckConstraint("status IN ('active','disabled','archived')", name="ck_platform_channels_status"),
        UniqueConstraint(
            "tenant_platform_id",
            "external_channel_id",
            "external_thread_id",
            name="uq_platform_channels_platform_channel_thread",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    tenant_platform_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenant_platforms.id"), nullable=False
    )
    external_channel_id: Mapped[str] = mapped_column(String, nullable=False)
    external_thread_id: Mapped[str | None] = mapped_column(String, nullable=True)
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    tenant_platform: Mapped[TenantPlatform] = relationship(back_populates="channels")
