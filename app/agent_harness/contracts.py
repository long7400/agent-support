"""Harness runtime contracts — typed state and context containers.

All contracts are serializable TypedDicts so they can be checkpointed,
logged, and replayed without custom serialization logic.
"""

from __future__ import annotations

from typing import Any, Literal, TypedDict
from uuid import UUID

from app.agent_harness.errors import TenantIdImmutableError

# ---------------------------------------------------------------------------
# Agent run state — the full runtime state for one harness invocation.
# ---------------------------------------------------------------------------


class AgentRunState(TypedDict, total=False):
    """Full runtime state for one harness invocation.

    Hydrated at start of run, mutated by middleware and the model/tool loop.
    ``tenant_id`` is immutable after initial hydration.
    """

    trace_id: str
    tenant_id: UUID
    input_event_id: str
    platform: Literal["telegram", "discord"]
    channel_id: str
    thread_id: str | None
    user_id_hash: str
    message_id: str
    inbound_text_preview: str
    messages: list[dict[str, Any]]
    tenant_context: dict[str, Any]
    platform_context: dict[str, Any]
    memory_context: dict[str, Any]
    available_capabilities: list[str]
    tool_results: list[dict[str, Any]]
    policy_decisions: list[dict[str, Any]]
    risk_signals: list[dict[str, Any]]
    budgets: dict[str, Any]
    final_response: dict[str, Any] | None
    audit_refs: list[str]


def apply_state_update(state: AgentRunState, update: dict[str, Any]) -> AgentRunState:
    """Apply a partial state update, rejecting tenant_id changes.

    Args:
        state: Current agent run state.
        update: Partial dict of fields to update.

    Returns:
        Updated agent run state (same dict, mutated in place).

    Raises:
        TenantIdImmutableError: If ``update`` contains a ``tenant_id`` that
            differs from the current ``state["tenant_id"]``.
    """
    if "tenant_id" in update:
        current = state.get("tenant_id")
        if current is not None and update["tenant_id"] != current:
            raise TenantIdImmutableError(
                f"Cannot change tenant_id from {current} to {update['tenant_id']} after hydration"
            )
    state.update(update)
    return state


# ---------------------------------------------------------------------------
# Harness context — per-run runtime context passed to middleware and tools.
# ---------------------------------------------------------------------------


class HarnessContext(TypedDict, total=False):
    """Per-run runtime context passed to middleware, tools, and model wrappers.

    Holds service handles, deadline, and run-mode configuration.
    Does NOT include decrypted secrets (those live in credential handles).
    """

    trace_id: str
    tenant_id: UUID
    deadline_ms: int
    run_mode: Literal["shadow", "propose", "enforce"]
    services: dict[str, Any]
    redaction_policy: dict[str, Any]


# ---------------------------------------------------------------------------
# Tenant harness profile — policy/config snapshot used by middleware.
# ---------------------------------------------------------------------------


class TenantHarnessProfile(TypedDict, total=False):
    """Policy and config snapshot for a tenant at the time of the run.

    Hydrated at the start of each harness run so middleware decisions are
    deterministic and auditable against a known profile version.
    """

    tenant_id: UUID
    config_version: int
    policy_version: int
    enabled_platforms: list[str]
    allowed_capabilities: list[str]
    model_policy: dict[str, Any]
    memory_policy: dict[str, Any]
    moderation_policy: dict[str, Any]
    escalation_policy: dict[str, Any]
    budgets: dict[str, Any]


# ---------------------------------------------------------------------------
# Trusted runtime event — the sanitised inbound event that enters the harness.
# ---------------------------------------------------------------------------


class TrustedRuntimeEvent(TypedDict, total=False):
    """A sanitised inbound event that enters the harness runtime.

    Built from a ChatEvent + ProcessingOutbox row by the runner.
    Contains no raw secrets, unvalidated payloads, or bot tokens.
    """

    event_id: UUID
    tenant_id: UUID
    chat_event_id: UUID
    platform: Literal["telegram", "discord"]
    channel_id: UUID
    thread_id: UUID | None
    user_id_hash: str
    message_type: str
    text_preview: str
    metadata: dict[str, Any]


# ---------------------------------------------------------------------------
# Harness result — the output of one harness run.
# ---------------------------------------------------------------------------


class HarnessResult(TypedDict, total=False):
    """The output of one successful harness run.

    Contains the final response, policy decisions made, and audit references
    so the caller can create delivery records without additional queries.
    """

    agent_run_id: UUID
    response_text: str
    response_metadata: dict[str, Any]
    policy_decisions: list[dict[str, Any]]
    tool_calls_made: list[dict[str, Any]]
    model_calls_made: list[dict[str, Any]]
    status: Literal["completed", "denied", "failed", "interrupted"]
    audit_refs: list[str]
