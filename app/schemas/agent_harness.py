"""Pydantic DTOs for the agent harness runtime — external API contracts."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AgentRunStepResponse(BaseModel):
    """A step recorded during an agent run (middleware, model, tool, capability)."""

    step_order: int = Field(..., description="Order of this step in the run")
    step_type: str = Field(..., description="middleware|model|tool|capability")
    step_name: str = Field(..., description="Name of the step")
    status: str = Field(..., description="completed|failed|denied|interrupted")
    started_at: datetime | None = Field(None, description="When the step started")
    completed_at: datetime | None = Field(None, description="When the step completed")
    latency_ms: int | None = Field(None, description="Duration in milliseconds")
    redacted_summary: str | None = Field(None, description="Bounded redacted summary")


class AgentRunResponse(BaseModel):
    """External response for an agent run query."""

    id: UUID = Field(..., description="Agent run ID")
    tenant_id: UUID = Field(..., description="Tenant scope")
    trace_id: str = Field(..., description="Correlation trace ID")
    harness_version: str = Field(..., description="Harness version used for the run")
    status: str = Field(..., description="completed|denied|failed|interrupted")
    started_at: datetime | None = Field(None, description="When the run started")
    completed_at: datetime | None = Field(None, description="When the run completed")
    latency_ms: int | None = Field(None, description="Duration in milliseconds")
    final_response_preview: str | None = Field(None, description="Bounded final response preview")
    steps: list[AgentRunStepResponse] = Field(default_factory=list, description="Steps in this run")
