"""Graph checkpoint metadata persistence model."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class GraphCheckpointMetadata(TimestampMixin, Base):
    """Maps thread_id to tenant_id and stores checkpoint metadata.

    Persists checkpoint identity and tenant binding so crash/resume can
    locate the right run without scanning the full graph state.
    """

    __tablename__ = "graph_checkpoint_metadata"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    thread_id: Mapped[str] = mapped_column(String, nullable=False)
    agent_run_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("agent_runs.id"), nullable=False
    )
    checkpoint_id: Mapped[str] = mapped_column(String, nullable=False)
    checkpoint_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB(astext_type=String()), nullable=False, default=dict
    )
