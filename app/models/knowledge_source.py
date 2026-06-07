"""KnowledgeSource model — top-level knowledge boundary owned by a tenant."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

SOURCE_TYPES = ("markdown", "zip")
SOURCE_STATUSES = ("active", "archived", "deleted")
SOURCE_VISIBILITIES = ("public", "private", "restricted")


class KnowledgeSource(TimestampMixin, Base):
    """A tenant-owned knowledge source (markdown upload, zip archive, …)."""

    __tablename__ = "knowledge_sources"
    __table_args__ = (
        CheckConstraint("source_type IN ('markdown','zip')", name="ck_knowledge_sources_source_type"),
        CheckConstraint(
            "status IN ('active','archived','deleted')",
            name="ck_knowledge_sources_status",
        ),
        CheckConstraint(
            "default_visibility IN ('public','private','restricted')",
            name="ck_knowledge_sources_default_visibility",
        ),
        UniqueConstraint("tenant_id", "slug", name="uq_knowledge_sources_tenant_slug"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, nullable=False)
    source_type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    default_visibility: Mapped[str] = mapped_column(String, nullable=False, default="private")
    locale: Mapped[str | None] = mapped_column(String, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_by_actor_type: Mapped[str] = mapped_column(String, nullable=False, default="operator")
    created_by_actor_id: Mapped[str] = mapped_column(String, nullable=False, default="system")
