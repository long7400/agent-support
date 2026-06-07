"""Risk policy middleware — evaluate inbound/outbound risk with shadow/propose/enforce modes."""

from __future__ import annotations

from typing import Any

from app.agent_harness.contracts import AgentRunState, HarnessContext


class RiskPolicyMiddleware:
    """Evaluate inbound/outbound risk with shadow/propose/enforce state machine.

    This middleware:
    - after_model: Evaluates risk signals from model output
    - after_agent: Makes final risk decision before outbound

    Risk modes (from TenantConfigVersion.moderation_mode):
    - shadow: Log risk signals but don't block (default in Phase 3)
    - propose: Flag risky content for human review
    - enforce: Block risky content immediately

    Phase 3 implements skeleton only. Real moderation comes in Phase 6.
    """

    # Risk signals to check (stub for Phase 3)
    RISK_SIGNALS = [
        "toxic_content",
        "spam",
        "phishing",
        "scam",
        "sensitive_data",
    ]

    def __init__(self, risk_detector: Any = None) -> None:
        """Initialize with optional risk detector.

        Args:
            risk_detector: Callable that detects risk signals.
                If None, uses default fake detector.
        """
        self._risk_detector = risk_detector or self._default_risk_detector

    async def _default_risk_detector(self, text: str, tenant_context: dict[str, Any]) -> list[dict[str, Any]]:
        """Default fake risk detector for Phase 3.

        Returns empty list (no risk detected) for all inputs.
        Real detection comes in Phase 6.
        """
        return []

    async def after_model(self, state: AgentRunState, context: HarnessContext) -> AgentRunState:
        """Evaluate risk signals from model output."""
        # Get latest message (model output)
        messages = state.get("messages", [])
        if not messages:
            return state

        last_message = messages[-1]
        content = last_message.get("content", "")

        # Detect risk signals
        tenant_context = state.get("tenant_context", {})
        signals = await self._risk_detector(content, tenant_context)

        # Store signals in state
        risk_signals = list(state.get("risk_signals", []))
        risk_signals.extend(signals)
        state["risk_signals"] = risk_signals

        return state

    async def after_agent(self, state: AgentRunState, context: HarnessContext) -> AgentRunState:
        """Make final risk decision before outbound."""
        risk_signals = state.get("risk_signals", [])

        # Get moderation mode from tenant profile
        tenant_context = state.get("tenant_context", {})
        profile = tenant_context.get("profile", {})
        moderation_policy = profile.get("moderation_policy", {})
        mode = moderation_policy.get("mode", "shadow")

        # Make decision based on mode and signals
        decision = {
            "middleware": "risk_policy",
            "mode": mode,
            "signals_detected": len(risk_signals),
        }

        if mode == "shadow":
            # Log but don't block
            decision["decision"] = "allowed_with_logging"
        elif mode == "propose":
            # Flag for human review (Phase 6 will implement actual review)
            decision["decision"] = "flagged_for_review"
        elif mode == "enforce":
            # Block if risk signals detected (Phase 6 will implement)
            if risk_signals:
                decision["decision"] = "blocked"
            else:
                decision["decision"] = "allowed"
        else:
            decision["decision"] = "allowed"

        # Record decision
        policy_decisions = list(state.get("policy_decisions", []))
        policy_decisions.append(decision)
        state["policy_decisions"] = policy_decisions

        return state
