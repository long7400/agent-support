"""Audit persistence model."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, JSON, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

class AuditEvent(TimestampMixin, Base):
    """Tenant-scoped audit event for privileged control-plane actions."""

    __tablename__ = "audit_events"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    actor_type: Mapped[str] = mapped_column(String, nullable=False)
    actor_id: Mapped[str] = mapped_column(String, nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    trace_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    before: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    tenant = relationship("Tenant", back_populates="audit_events")
