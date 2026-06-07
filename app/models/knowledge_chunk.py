"""KnowledgeChunk model — an indexed text fragment with citation metadata."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

CHUNK_VISIBILITIES = ("public", "private", "restricted")


class KnowledgeChunk(TimestampMixin, Base):
    """An individual text chunk with citation context and visibility."""

    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        CheckConstraint(
            "visibility IN ('public','private','restricted')",
            name="ck_knowledge_chunks_visibility",
        ),
        Index("idx_knowledge_chunks_tenant_source", "tenant_id", "source_id"),
        Index(
            "idx_knowledge_chunks_tenant_version_active",
            "tenant_id",
            "source_version_id",
            "is_active",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    source_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("knowledge_sources.id"), nullable=False, index=True
    )
    source_version_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("knowledge_source_versions.id"), nullable=False, index=True
    )
    document_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("knowledge_documents.id"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    text_hash: Mapped[str] = mapped_column(String, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_path: Mapped[str | None] = mapped_column(String, nullable=True)
    source_uri: Mapped[str | None] = mapped_column(String, nullable=True)
    source_title: Mapped[str | None] = mapped_column(String, nullable=True)
    visibility: Mapped[str] = mapped_column(String, nullable=False, default="private")
    locale: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    lexical_tokens: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
