"""KnowledgeSourceVersion model — immutable snapshot of a source at processing stage."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Integer, JSON, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

VERSION_STATUSES = (
    "parsing",
    "chunked",
    "embedded",
    "indexed",
    "verified",
    "active",
    "tombstoned",
    "failed",
)


class KnowledgeSourceVersion(TimestampMixin, Base):
    """Immutable version capturing state at a processing milestone."""

    __tablename__ = "knowledge_source_versions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('parsing','chunked','embedded','indexed','verified','active','tombstoned','failed')",
            name="ck_knowledge_source_versions_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    source_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("knowledge_sources.id"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="parsing")
    content_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    chunk_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    document_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String, nullable=True)
    embedding_dim: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    activated_at: Mapped[datetime | None] = mapped_column(nullable=True)
    tombstoned_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_by_actor_type: Mapped[str] = mapped_column(String, nullable=False, default="operator")
    created_by_actor_id: Mapped[str] = mapped_column(String, nullable=False, default="system")
