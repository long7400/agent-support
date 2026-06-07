"""Agent run step persistence model."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

STEP_TYPES = ("middleware", "model", "tool", "capability")
STEP_STATUSES = ("completed", "failed", "denied", "interrupted", "skipped")


class AgentRunStep(TimestampMixin, Base):
    """One step in an agent run (middleware, model, tool, capability).

    Captures step order, type, name, status, latency, and a bounded
    redacted summary. Metadata holds bounded step-specific context.
    """

    __tablename__ = "agent_run_steps"
    __table_args__ = (
        CheckConstraint(
            "step_type IN ('middleware','model','tool','capability')",
            name="ck_agent_run_steps_step_type",
        ),
        CheckConstraint(
            "status IN ('completed','failed','denied','interrupted','skipped')",
            name="ck_agent_run_steps_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_run_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("agent_runs.id"), nullable=False)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    step_type: Mapped[str] = mapped_column(String, nullable=False)
    step_name: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[datetime] = mapped_column(nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    redacted_summary: Mapped[str | None] = mapped_column(String, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB(astext_type=String()), nullable=False, default=dict)
