"""Capability registry middleware — expose only tenant/role/node-allowed tools and delegated agents."""

from __future__ import annotations

from typing import Any

from app.agent_harness.contracts import AgentRunState, HarnessContext


class CapabilityRegistryMiddleware:
    """Expose only capabilities allowed by tenant profile.

    This middleware runs in before_model and:
    - Filters available capabilities based on tenant profile
    - Records which capabilities are exposed in state
    - Audits denied capabilities

    Phase 3 uses fake capabilities only. Real capabilities come in Phase 5.
    """

    # All known capabilities in the system
    ALL_CAPABILITIES = [
        "rag.search",
        "tool.web_search",
        "tool.calculator",
        "tool.code_execution",
        "agent.delegated_support",
    ]

    def __init__(self, capability_filter: Any = None) -> None:
        """Initialize with optional capability filter.

        Args:
            capability_filter: Callable that filters capabilities based on profile.
                If None, uses default filter that respects allowed_capabilities.
        """
        self._capability_filter = capability_filter or self._default_capability_filter

    async def _default_capability_filter(self, all_capabilities: list[str], profile: dict[str, Any]) -> list[str]:
        """Default capability filter for Phase 3."""
        allowed = set(profile.get("allowed_capabilities", []))

        # Filter to only allowed capabilities
        return [cap for cap in all_capabilities if cap in allowed]

    async def before_model(self, state: AgentRunState, context: HarnessContext) -> AgentRunState:
        """Filter capabilities based on tenant profile."""
        tenant_context = state.get("tenant_context", {})
        profile = tenant_context.get("profile", {})

        # Filter capabilities
        allowed_capabilities = await self._capability_filter(self.ALL_CAPABILITIES, profile)

        # Store in state
        state["available_capabilities"] = allowed_capabilities

        # Audit denied capabilities
        denied = [cap for cap in self.ALL_CAPABILITIES if cap not in allowed_capabilities]

        if denied:
            policy_decisions = list(state.get("policy_decisions", []))
            policy_decisions.append(
                {
                    "middleware": "capability_registry",
                    "decision": "filtered",
                    "allowed": allowed_capabilities,
                    "denied": denied,
                }
            )
            state["policy_decisions"] = policy_decisions

        return state
