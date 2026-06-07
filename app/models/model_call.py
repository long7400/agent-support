"""Model call persistence model."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

MODEL_CALL_STATUSES = ("completed", "failed", "timeout", "denied")


class ModelCall(TimestampMixin, Base):
    """One LLM model call during an agent run.

    Captures provider/model, prompt version, cost, tokens, and status.
    Phase 3 uses FakeModel so all values are deterministic mock data.
    """

    __tablename__ = "model_calls"
    __table_args__ = (
        CheckConstraint(
            "status IN ('completed','failed','timeout','denied')",
            name="ck_model_calls_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_run_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("agent_runs.id"), nullable=False)
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    step_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("agent_run_steps.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    model_name: Mapped[str] = mapped_column(String, nullable=False)
    prompt_version: Mapped[str | None] = mapped_column(String, nullable=True)
    mock_cost: Mapped[str] = mapped_column(String, nullable=False, default="0.0")
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String, nullable=False, default="completed")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB(astext_type=String()), nullable=False, default=dict)
