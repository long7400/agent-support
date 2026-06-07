"""AgentHarnessRuntime — orchestrates one agent run through the middleware stack.

Lifecycle:
  1. Hydrate AgentRunState from TrustedRuntimeEvent + profile
  2. Run middleware before_agent hooks
  3. Loop: model call -> tool calls (via middleware)
  4. Run middleware after_agent hooks
  5. Build HarnessResult
  6. Persist run/step/model records via repositories
"""

from __future__ import annotations

from datetime import datetime, UTC
from collections.abc import Awaitable, Callable
from typing import cast
from uuid import UUID, uuid4

from app.agent_harness.contracts import (
    AgentRunState,
    HarnessContext,
    HarnessResult,
    TenantHarnessProfile,
    TrustedRuntimeEvent,
)
from app.agent_harness.errors import HarnessRunError, TenantDisabledError, CapabilityDeniedError, PolicyDeniedError
from app.agent_harness.middleware.base import Middleware
from app.agent_harness.models.fake_model import FakeModel
from app.agent_harness.capabilities.registry import FakeCapabilityRegistry


class AgentHarnessRuntime:
    """Orchestrates one agent run: middleware -> model/tool loop -> result.

    Phase 3: deterministic, fake model only, no real LLM or external tools.
    """

    def __init__(
        self,
        model: FakeModel,
        capability_registry: FakeCapabilityRegistry,
        middleware_stack: list[Middleware],
    ) -> None:
        """Initialize the runtime.

        Args:
            model: The model instance (FakeModel in Phase 3).
            capability_registry: Registry for tool/capability execution.
            middleware_stack: Ordered list of Middleware instances.
        """
        self._model = model
        self._middleware_stack = middleware_stack
        self._run_mode = "shadow"

    async def run(
        self,
        event: TrustedRuntimeEvent,
        profile: TenantHarnessProfile,
        agent_run_id: UUID | None = None,
    ) -> HarnessResult:
        """Execute one harness run.

        Args:
            event: The trusted runtime event to process.
            profile: Tenant harness profile with policy settings.
            agent_run_id: Optional persisted run ID to reuse.

        Returns:
            HarnessResult with final response, policy decisions, and audit refs.

        Raises:
            TenantDisabledError: If tenant is disabled/suspended.
            HarnessRunError: On unrecoverable run failure.
        """
        agent_run_id = agent_run_id or uuid4()
        start_time = datetime.now(UTC)

        # 1. Hydrate state
        state = self._hydrate_state(event, agent_run_id, profile)
        context = self._build_context(event, agent_run_id)

        try:
            # 2. Run middleware before_agent (only if hook exists)
            for mw in self._middleware_stack:
                hook = getattr(mw, "before_agent", None)
                if hook is not None:
                    await hook(state, context)

            # 3. Record run step metadata
            await self._record_step(state, context, "middleware", "before_agent", "completed")

            # 4. Loop: model call -> tool calls
            model_response = await self._run_model_loop(state, context)
        except TenantDisabledError:
            return self._build_denied_result(agent_run_id, state)
        except (CapabilityDeniedError, PolicyDeniedError) as exc:
            return self._build_policy_denied_result(agent_run_id, state, str(exc))
        except Exception as exc:
            raise HarnessRunError(f"Harness run failed: {exc}") from exc

        # 5. Build final response
        state["final_response"] = {"text": model_response}

        # 6. Run middleware after_agent (only if hook exists)
        for mw in self._middleware_stack:
            hook = getattr(mw, "after_agent", None)
            if hook is not None:
                await hook(state, context)

        # 7. Build result
        latency_ms = int((datetime.now(UTC) - start_time).total_seconds() * 1000)
        return HarnessResult(
            agent_run_id=agent_run_id,
            response_text=model_response,
            response_metadata=state.get("final_response") or {},
            policy_decisions=state.get("policy_decisions", []),
            tool_calls_made=state.get("tool_results", []),
            model_calls_made=state.get("model_calls_made", []),
            status="completed",
            audit_refs=state.get("audit_refs", []),
            latency_ms=latency_ms,
        )

    def _hydrate_state(
        self,
        event: TrustedRuntimeEvent,
        agent_run_id: UUID,
        profile: TenantHarnessProfile,
    ) -> AgentRunState:
        """Hydrate AgentRunState from a TrustedRuntimeEvent."""
        messages = [
            {"role": "user", "content": event.get("text_preview", "")},
        ]
        state = cast(AgentRunState, {
            "trace_id": str(event.get("event_id", "")),
            "tenant_id": event.get("tenant_id"),
            "input_event_id": str(event.get("chat_event_id", "")),
            "platform": event.get("platform", "telegram"),
            "channel_id": str(event.get("channel_id", "")),
            "thread_id": str(event.get("thread_id", "")) if event.get("thread_id") else None,
            "user_id_hash": event.get("user_id_hash", ""),
            "message_id": str(event.get("chat_event_id", "")),
            "inbound_text_preview": event.get("text_preview", ""),
            "messages": messages,
            "tenant_context": {"profile": profile},
            "platform_context": {},
            "memory_context": {},
            "available_capabilities": [],
            "tool_results": [],
            "policy_decisions": [],
            "risk_signals": [],
            "budgets": {},
            "final_response": None,
            "audit_refs": [str(agent_run_id)],
        })
        return state

    def _build_context(
        self,
        event: TrustedRuntimeEvent,
        agent_run_id: UUID,
    ) -> HarnessContext:
        """Build HarnessContext from event data."""
        return cast(HarnessContext, {
            "trace_id": str(event.get("event_id", "")),
            "tenant_id": event.get("tenant_id"),
            "deadline_ms": 30000,
            "run_mode": self._run_mode,
            "services": {},
            "redaction_policy": {},
        })

    async def _run_model_loop(
        self,
        state: AgentRunState,
        context: HarnessContext,
    ) -> str:
        """Execute the model/tool loop.

        Phase 3: simple single-pass model with fixture response.
        Full tool-call loop arrives in Phase 4.
        """
        # Run before_model hooks (only if hook exists)
        for mw in self._middleware_stack:
            hook = getattr(mw, "before_model", None)
            if hook is not None:
                await hook(state, context)

        async def model_call() -> str:
            return await self._model.generate(state, context)

        wrapped_call: Callable[[], Awaitable[str]] = model_call
        for mw in reversed(self._middleware_stack):
            hook = getattr(mw, "wrap_model_call", None)
            if hook is None:
                continue

            next_call = wrapped_call

            async def call_with_middleware(
                hook=hook,
                next_call: Callable[[], Awaitable[str]] = next_call,
            ) -> str:
                return cast(str, await hook(state, context, next_call))

            wrapped_call = call_with_middleware

        result = await wrapped_call()

        # Run after_model hooks (only if hook exists)
        for mw in self._middleware_stack:
            hook = getattr(mw, "after_model", None)
            if hook is not None:
                await hook(state, context)

        return result

    async def _record_step(
        self,
        state: AgentRunState,
        context: HarnessContext,
        step_type: str,
        step_name: str,
        status: str,
    ) -> None:
        """Record a step in the state for persistence later."""
        steps = state.setdefault("_steps", [])
        steps.append(
            {
                "type": step_type,
                "name": step_name,
                "status": status,
            }
        )

    def _build_denied_result(
        self,
        agent_run_id: UUID,
        state: AgentRunState,
    ) -> HarnessResult:
        """Build a denied HarnessResult."""
        return HarnessResult(
            agent_run_id=agent_run_id,
            response_text="",
            response_metadata={},
            policy_decisions=state.get("policy_decisions", []),
            tool_calls_made=[],
            model_calls_made=[],
            status="denied",
            audit_refs=state.get("audit_refs", []),
            latency_ms=0,
        )

    def _build_policy_denied_result(
        self,
        agent_run_id: UUID,
        state: AgentRunState,
        reason: str,
    ) -> HarnessResult:
        """Build a HarnessResult for policy denial."""
        return HarnessResult(
            agent_run_id=agent_run_id,
            response_text="",
            response_metadata={"denial_reason": reason},
            policy_decisions=state.get("policy_decisions", []) + [{"reason": reason, "type": "capability_denied"}],
            tool_calls_made=[],
            model_calls_made=[],
            status="denied",
            audit_refs=state.get("audit_refs", []),
            latency_ms=0,
        )
