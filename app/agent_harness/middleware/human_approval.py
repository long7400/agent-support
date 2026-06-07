"""Human approval middleware — interrupt/pause placeholder for later moderation/tools."""

from __future__ import annotations

from typing import Any

from app.agent_harness.contracts import AgentRunState, HarnessContext


class HumanApprovalMiddleware:
    """Interrupt/pause placeholder for destructive, high-risk, or expensive capabilities.

    This middleware runs in wrap_tool_call and can interrupt before:
    - Destructive actions (delete, modify sensitive data)
    - High-risk actions (financial transactions, credential exposure)
    - Expensive actions (high cost, long-running operations)

    Phase 3 implements skeleton only. Real HITL approval comes in Phase 6.

    When implemented, this will:
    - Check if action requires approval
    - If yes, raise an interrupt via LangGraph checkpoint
    - Pause execution until approval/rejection
    - Resume after approval
    """

    # Tools that require approval (stub for Phase 3)
    TOOLS_REQUIRING_APPROVAL = [
        # Phase 5+ will add real tools here
        # "tool.delete_data",
        # "tool.send_email",
        # "tool.financial_transaction",
    ]

    def __init__(self, approval_checker: Any = None) -> None:
        """Initialize with optional approval checker.

        Args:
            approval_checker: Callable that checks if tool requires approval.
                If None, uses default checker.
        """
        self._approval_checker = approval_checker or self._default_approval_checker

    async def _default_approval_checker(
        self, tool_name: str, tool_args: dict[str, Any], profile: dict[str, Any]
    ) -> bool:
        """Default approval checker for Phase 3.

        Returns False (no approval required) for all tools.
        Real approval logic comes in Phase 6.
        """
        # Check if tool is in approval-required list
        return tool_name in self.TOOLS_REQUIRING_APPROVAL

    async def wrap_tool_call(
        self,
        state: AgentRunState,
        context: HarnessContext,
        tool_name: str,
        tool_args: dict[str, Any],
        call: Any,
    ) -> Any:
        """Check if tool requires approval before execution."""
        tenant_context = state.get("tenant_context", {})
        profile = tenant_context.get("profile", {})

        requires_approval = await self._approval_checker(tool_name, tool_args, profile)

        if requires_approval:
            # Phase 3: Record that approval would be required
            # Phase 6: Actually interrupt and wait for approval
            decision = {
                "middleware": "human_approval",
                "decision": "approval_required",
                "tool": tool_name,
                "status": "pending_implementation",  # Phase 3 skeleton
            }
            decisions = list(state.get("policy_decisions", []))
            decisions.append(decision)
            state["policy_decisions"] = decisions

            # In Phase 3, we log but don't actually interrupt
            # In Phase 6, this would raise a LangGraph interrupt

        # Execute tool (Phase 3 always executes, Phase 6 would wait for approval)
        result = await call()

        return result
