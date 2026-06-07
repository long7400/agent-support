"""Tenant context middleware — loads tenant status and fails closed if disabled."""

from __future__ import annotations

from typing import Any

from app.agent_harness.contracts import AgentRunState, HarnessContext, TenantHarnessProfile
from app.agent_harness.errors import TenantDisabledError


class TenantContextMiddleware:
    """Load tenant status/profile; disabled tenant stops before model/tool/outbound.

    This middleware runs in before_agent and:
    - Validates tenant is active
    - Loads the tenant harness profile into state
    - Records the decision in policy_decisions

    If the tenant is disabled/suspended, raises TenantDisabledError immediately.
    """

    def __init__(self, profile_loader: Any = None) -> None:
        """Initialize with optional profile loader.

        Args:
            profile_loader: Callable that loads TenantHarnessProfile for a tenant.
                If None, uses a default fake profile (for testing).
        """
        self._profile_loader = profile_loader or self._default_profile_loader

    async def _default_profile_loader(self, tenant_id: Any) -> TenantHarnessProfile:
        """Default fake profile loader for Phase 3."""
        return TenantHarnessProfile(
            tenant_id=tenant_id,
            config_version=1,
            policy_version=1,
            enabled_platforms=["telegram", "discord"],
            allowed_capabilities=["rag.search"],
            model_policy={"max_calls": 10, "timeout_ms": 5000},
            memory_policy={"max_tokens": 1000},
            moderation_policy={"mode": "shadow"},
            escalation_policy={"enabled": False},
            budgets={"max_cost": "1.0", "max_tokens": 10000},
        )

    async def before_agent(self, state: AgentRunState, context: HarnessContext) -> AgentRunState:
        """Load tenant profile and validate tenant is active.

        Raises TenantDisabledError if tenant is not active.
        """
        tenant_id = state.get("tenant_id")
        if tenant_id is None:
            raise TenantDisabledError("tenant_id is None; cannot load profile")

        # Load profile
        profile = await self._profile_loader(tenant_id)

        # Check tenant status (in Phase 3 we assume active unless profile says otherwise)
        # In production, this would check tenant.status from DB
        tenant_status = state.get("tenant_context", {}).get("status", "active")

        if tenant_status in ("disabled", "suspended"):
            # Record denial in policy_decisions
            decision = {
                "middleware": "tenant_context",
                "decision": "denied",
                "reason": f"tenant_status={tenant_status}",
                "tenant_id": str(tenant_id),
            }
            decisions = list(state.get("policy_decisions", []))
            decisions.append(decision)
            state["policy_decisions"] = decisions

            raise TenantDisabledError(f"Tenant {tenant_id} is {tenant_status}; cannot process request")

        # Store profile in state for downstream middleware
        state["tenant_context"] = {
            **state.get("tenant_context", {}),
            "profile": profile,
            "config_version": profile.get("config_version", 1),
            "policy_version": profile.get("policy_version", 1),
            "enabled_platforms": profile.get("enabled_platforms", []),
            "allowed_capabilities": profile.get("allowed_capabilities", []),
        }

        # Record success decision
        decision = {
            "middleware": "tenant_context",
            "decision": "allowed",
            "tenant_id": str(tenant_id),
            "config_version": profile.get("config_version", 1),
        }
        decisions = list(state.get("policy_decisions", []))
        decisions.append(decision)
        state["policy_decisions"] = decisions

        return state
