"""Repository methods for creating and updating harness runtime records.

All methods accept an async SQLAlchemy session and write within the caller's
tenant context.  No raw SQL — all operations go through ORM models.
"""

from __future__ import annotations

from datetime import datetime, UTC
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_run import AgentRun
from app.models.agent_run_step import AgentRunStep
from app.models.model_call import ModelCall
from app.models.graph_checkpoint_metadata import GraphCheckpointMetadata


async def create_agent_run(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    processing_outbox_id: UUID | None = None,
    trace_id: str,
    input_event_id: str,
    harness_version: str,
    middleware_sequence: list[Any] | None = None,
    config_version: int = 1,
    policy_version: int = 1,
) -> AgentRun:
    """Create a new agent run record.

    Args:
        session: Database session inside tenant context.
        tenant_id: Owning tenant.
        processing_outbox_id: Optional link to the processing outbox row.
        trace_id: Correlation trace ID.
        input_event_id: ID of the trusted runtime event.
        harness_version: Harness version string.
        middleware_sequence: Ordered list of middleware names/configs.
        config_version: Tenant config version snapshot.
        policy_version: Tenant policy version snapshot.

    Returns:
        The newly created AgentRun ORM instance.
    """
    run = AgentRun(
        id=uuid4(),
        tenant_id=tenant_id,
        processing_outbox_id=processing_outbox_id,
        trace_id=trace_id,
        input_event_id=input_event_id,
        harness_version=harness_version,
        middleware_sequence=middleware_sequence or [],
        config_version=config_version,
        policy_version=policy_version,
        status="running",
        started_at=datetime.now(UTC),
    )
    session.add(run)
    await session.flush()
    return run


async def complete_agent_run(
    session: AsyncSession,
    *,
    agent_run_id: UUID,
    status: str,
    final_response_preview: str | None = None,
    latency_ms: int | None = None,
) -> None:
    """Mark an agent run as completed/failed/denied/interrupted.

    Args:
        session: Database session inside tenant context.
        agent_run_id: ID of the agent run to complete.
        status: Final status (completed, denied, failed, interrupted).
        final_response_preview: Bounded preview of the final response.
        latency_ms: Total run duration in milliseconds.
    """
    now = datetime.now(UTC)
    stmt = select(AgentRun).where(AgentRun.id == agent_run_id)
    result = await session.execute(stmt)
    run = result.scalar_one_or_none()
    if run is None:
        return
    run.status = status
    run.completed_at = now
    run.latency_ms = latency_ms
    if final_response_preview is not None:
        run.final_response_preview = final_response_preview[:500]  # bounded
    await session.flush()


async def create_agent_run_step(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    agent_run_id: UUID,
    step_order: int,
    step_type: str,
    step_name: str,
    status: str = "completed",
    redacted_summary: str | None = None,
) -> AgentRunStep:
    """Create a new step record within an agent run.

    Args:
        session: Database session inside tenant context.
        tenant_id: Owning tenant.
        agent_run_id: ID of the parent agent run.
        step_order: Ordinal position of this step in the run.
        step_type: One of middleware, model, tool, capability.
        step_name: Human-readable step name.
        status: Step status (completed, failed, denied, interrupted).
        redacted_summary: Bounded redacted step summary.

    Returns:
        The newly created AgentRunStep ORM instance.
    """
    step = AgentRunStep(
        tenant_id=tenant_id,
        agent_run_id=agent_run_id,
        step_order=step_order,
        step_type=step_type,
        step_name=step_name,
        status=status,
        started_at=datetime.now(UTC),
        redacted_summary=redacted_summary[:1000] if redacted_summary else None,  # bounded
    )
    session.add(step)
    await session.flush()
    return step


async def complete_agent_run_step(
    session: AsyncSession,
    *,
    step_id: UUID,
    status: str,
    redacted_summary: str | None = None,
) -> None:
    """Mark a step as completed/failed/denied/interrupted.

    Args:
        session: Database session inside tenant context.
        step_id: ID of the step to complete.
        status: Final step status.
        redacted_summary: Optional bounded redacted summary.
    """
    now = datetime.now(UTC)
    stmt = select(AgentRunStep).where(AgentRunStep.id == step_id)
    result = await session.execute(stmt)
    step = result.scalar_one_or_none()
    if step is None:
        return
    step.status = status
    step.completed_at = now
    if step.started_at:
        step.latency_ms = int((now - step.started_at).total_seconds() * 1000)
    if redacted_summary is not None:
        step.redacted_summary = redacted_summary[:1000]
    await session.flush()


async def create_model_call(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    agent_run_id: UUID,
    step_id: UUID | None = None,
    provider: str = "fake",
    model_name: str = "fake-model",
    prompt_version: str | None = None,
    mock_cost: int | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
) -> ModelCall:
    """Create a new model call record.

    Args:
        session: Database session inside tenant context.
        tenant_id: Owning tenant.
        agent_run_id: ID of the parent agent run.
        step_id: Optional link to the agent run step.
        provider: Model provider name.
        model_name: Model name.
        prompt_version: Prompt version identifier.
        mock_cost: Mock cost in integer units.
        input_tokens: Number of input tokens.
        output_tokens: Number of output tokens.

    Returns:
        The newly created ModelCall ORM instance.
    """
    mc = ModelCall(
        tenant_id=tenant_id,
        agent_run_id=agent_run_id,
        step_id=step_id,
        provider=provider,
        model_name=model_name,
        prompt_version=prompt_version,
        mock_cost=mock_cost,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        status="completed",
    )
    session.add(mc)
    await session.flush()
    return mc


async def create_checkpoint_metadata(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    thread_id: str,
    agent_run_id: UUID,
    checkpoint_id: str,
    checkpoint_data: dict[str, Any] | None = None,
) -> GraphCheckpointMetadata:
    """Create a new graph checkpoint metadata record.

    Args:
        session: Database session inside tenant context.
        tenant_id: Owning tenant.
        thread_id: LangGraph thread ID.
        agent_run_id: ID of the parent agent run.
        checkpoint_id: LangGraph checkpoint ID.
        checkpoint_data: Arbitrary checkpoint metadata (bounded).

    Returns:
        The newly created GraphCheckpointMetadata ORM instance.
    """
    rec = GraphCheckpointMetadata(
        tenant_id=tenant_id,
        thread_id=thread_id,
        agent_run_id=agent_run_id,
        checkpoint_id=checkpoint_id,
        checkpoint_data=checkpoint_data or {},
    )
    session.add(rec)
    await session.flush()
    return rec
