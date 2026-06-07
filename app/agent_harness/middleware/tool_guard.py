"""Tool guard middleware — validate args, permission, risk, timeout, audit around tool calls."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from app.agent_harness.contracts import AgentRunState, HarnessContext
from app.agent_harness.errors import CapabilityDeniedError


class ToolGuardMiddleware:
    """Validate and audit tool invocations.

    This middleware runs in wrap_tool_call and:
    - Checks if the tool is in the available capabilities
    - Validates tool arguments (schema validation stub in Phase 3)
    - Enforces timeout (stub in Phase 3)
    - Audits all tool calls and denials
    - Never calls the tool body when denied

    Phase 3 uses fake tools. Real tool validation comes in Phase 5.
    """

    # Tool argument schemas (stub for Phase 3)
    TOOL_SCHEMAS = {
        "rag.search": {
            "required": ["query"],
            "optional": [
                "candidate_top_k",
                "final_top_k",
                "locale",
                "min_score",
                "retrieval_denied",
                "retrieval_mode",
                "source_allowlist",
                "source_version_ids",
                "visibility",
            ],
        },
    }

    def __init__(self, validator: Any = None) -> None:
        """Initialize with optional argument validator.

        Args:
            validator: Callable that validates tool arguments.
                If None, uses default schema validator.
        """
        self._validator = validator or self._default_validator

    async def _default_validator(self, tool_name: str, tool_args: dict[str, Any]) -> tuple[bool, str | None]:
        """Default argument validator for Phase 3.

        Returns:
            Tuple of (is_valid, error_message)
        """
        schema = self.TOOL_SCHEMAS.get(tool_name)
        if schema is None:
            # Unknown tool — deny
            return False, f"Unknown tool: {tool_name}"

        # Check required args
        required = schema.get("required", [])
        for arg in required:
            if arg not in tool_args:
                return False, f"Missing required argument: {arg}"

        return True, None

    async def wrap_tool_call(
        self,
        state: AgentRunState,
        context: HarnessContext,
        tool_name: str,
        tool_args: dict[str, Any],
        call: Callable[[], Awaitable[Any]],
    ) -> Any:
        """Validate and audit tool invocation."""
        available_capabilities = state.get("available_capabilities", [])

        # Check if tool is available
        if tool_name not in available_capabilities:
            # Record denial
            decision = {
                "middleware": "tool_guard",
                "decision": "denied",
                "tool": tool_name,
                "reason": "capability_not_available",
            }
            decisions = list(state.get("policy_decisions", []))
            decisions.append(decision)
            state["policy_decisions"] = decisions

            # Track in tool results
            tool_results = list(state.get("tool_results", []))
            tool_results.append(
                {
                    "tool": tool_name,
                    "status": "denied",
                    "reason": "capability_not_available",
                }
            )
            state["tool_results"] = tool_results

            raise CapabilityDeniedError(f"Tool {tool_name} is not available for this run")

        # Validate arguments
        is_valid, error = await self._validator(tool_name, tool_args)
        if not is_valid:
            # Record denial
            decision = {
                "middleware": "tool_guard",
                "decision": "denied",
                "tool": tool_name,
                "reason": f"invalid_args: {error}",
            }
            decisions = list(state.get("policy_decisions", []))
            decisions.append(decision)
            state["policy_decisions"] = decisions

            tool_results = list(state.get("tool_results", []))
            tool_results.append(
                {
                    "tool": tool_name,
                    "status": "denied",
                    "reason": f"invalid_args: {error}",
                }
            )
            state["tool_results"] = tool_results

            raise CapabilityDeniedError(f"Tool {tool_name} argument validation failed: {error}")

        # Execute tool
        try:
            result = await call()

            # Record success
            decision = {
                "middleware": "tool_guard",
                "decision": "allowed",
                "tool": tool_name,
            }
            decisions = list(state.get("policy_decisions", []))
            decisions.append(decision)
            state["policy_decisions"] = decisions

            tool_results = list(state.get("tool_results", []))
            tool_results.append(
                {
                    "tool": tool_name,
                    "status": "success",
                    "result_preview": str(result)[:200],  # Bounded preview
                }
            )
            state["tool_results"] = tool_results

            return result
        except Exception as e:
            # Record failure
            tool_results = list(state.get("tool_results", []))
            tool_results.append(
                {
                    "tool": tool_name,
                    "status": "failed",
                    "error": str(e)[:200],  # Bounded error
                }
            )
            state["tool_results"] = tool_results
            raise
