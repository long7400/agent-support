"""KnowledgeSyncJob model — tracks one idempotent sync run for a source version."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

SYNC_JOB_STATUSES = ("queued", "running", "succeeded", "failed", "cancelled")


class KnowledgeSyncJob(TimestampMixin, Base):
    """An idempotent sync job processing a source version through the pipeline."""

    __tablename__ = "knowledge_sync_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued','running','succeeded','failed','cancelled')",
            name="ck_knowledge_sync_jobs_status",
        ),
        UniqueConstraint(
            "tenant_id", "idempotency_key", name="uq_knowledge_sync_jobs_tenant_idempotency"
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
    status: Mapped[str] = mapped_column(String, nullable=False, default="queued")
    idempotency_key: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    documents_processed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunks_embedded: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vectors_upserted: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lexical_indexed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    errors_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_log: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
