"""Agent run persistence model."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Integer, JSON, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

AGENT_RUN_STATUSES = ("pending", "running", "completed", "denied", "failed", "interrupted")


class AgentRun(TimestampMixin, Base):
    """Top-level audit record for one harness invocation.

    Captures the trace, harness version, middleware sequence, config/policy
    versions, status, latency, and a bounded final response preview.
    """

    __tablename__ = "agent_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','running','completed','denied','failed','interrupted')",
            name="ck_agent_runs_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    processing_outbox_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("processing_outbox.id"), nullable=True
    )
    trace_id: Mapped[str] = mapped_column(String, nullable=False)
    input_event_id: Mapped[str] = mapped_column(String, nullable=False)
    harness_version: Mapped[str] = mapped_column(String, nullable=False)
    middleware_sequence: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    config_version: Mapped[int] = mapped_column(Integer, nullable=False)
    policy_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    started_at: Mapped[datetime] = mapped_column(nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    final_response_preview: Mapped[str | None] = mapped_column(String, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB(astext_type=String()), nullable=False, default=dict
    )
