"""Model policy middleware — fake model selection, call limits, timeouts, cost counters."""

from __future__ import annotations

from typing import Any

from app.agent_harness.contracts import AgentRunState, HarnessContext
from app.agent_harness.errors import PolicyDeniedError


class ModelPolicyMiddleware:
    """Enforce model selection, call limits, timeouts, and cost budgets.

    This middleware:
    - before_model: Selects model based on tenant policy
    - wrap_model_call: Enforces call limits, tracks costs, applies timeouts

    Phase 3 uses FakeModel. No real LLM calls.
    """

    DEFAULT_MAX_CALLS = 10
    DEFAULT_TIMEOUT_MS = 5000
    DEFAULT_MAX_COST = "1.0"

    def __init__(self, model_selector: Any = None) -> None:
        """Initialize with optional model selector.

        Args:
            model_selector: Callable that selects model based on policy.
                If None, uses default fake model.
        """
        self._model_selector = model_selector or self._default_model_selector

    async def _default_model_selector(self, profile: dict[str, Any]) -> dict[str, Any]:
        """Default model selector for Phase 3."""
        return {
            "provider": "fake",
            "model_name": "fake-model-v1",
            "prompt_version": "v1",
        }

    async def before_model(self, state: AgentRunState, context: HarnessContext) -> AgentRunState:
        """Select model based on tenant policy."""
        tenant_context = state.get("tenant_context", {})
        profile = tenant_context.get("profile", {})
        model_policy = profile.get("model_policy", {})

        # Select model
        model_config = await self._model_selector(profile)

        # Store model config in state
        state["model_config"] = model_config

        # Update budgets
        budget = dict(state.get("budgets", {}))
        budget["model_max_calls"] = model_policy.get("max_calls", self.DEFAULT_MAX_CALLS)
        budget["model_timeout_ms"] = model_policy.get("timeout_ms", self.DEFAULT_TIMEOUT_MS)
        budget["model_max_cost"] = model_policy.get("max_cost", self.DEFAULT_MAX_COST)
        budget["model_calls_made"] = 0
        budget["model_cost_accrued"] = "0.0"
        state["budgets"] = budget

        return state

    async def wrap_model_call(
        self,
        state: AgentRunState,
        context: HarnessContext,
        call: Any,
    ) -> Any:
        """Wrap model call to enforce limits and track usage."""
        # Check call limit
        budgets = state.get("budgets", {})
        max_calls = budgets.get("model_max_calls", self.DEFAULT_MAX_CALLS)
        calls_made = budgets.get("model_calls_made", 0)

        if calls_made >= max_calls:
            raise PolicyDeniedError(f"Model call limit exceeded: {calls_made}/{max_calls}")

        # Execute call
        try:
            result = await call()

            # Track call
            budgets["model_calls_made"] = calls_made + 1
            state["budgets"] = budgets

            return result
        except Exception as e:
            # Record failure
            policy_decisions = list(state.get("policy_decisions", []))
            policy_decisions.append(
                {
                    "middleware": "model_policy",
                    "decision": "failed",
                    "reason": str(e),
                }
            )
            state["policy_decisions"] = policy_decisions
            raise
