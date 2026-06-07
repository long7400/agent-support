"""Middleware base protocol for the agent harness."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Protocol, runtime_checkable

from app.agent_harness.contracts import AgentRunState, HarnessContext


@runtime_checkable
class Middleware(Protocol):
    """Protocol for harness middleware.

    Each middleware can hook into different phases of the agent run lifecycle:
    - before_agent: runs before the agent loop starts
    - before_model: runs before each model invocation
    - after_model: runs after each model invocation
    - after_agent: runs after the agent loop completes
    - wrap_model_call: wraps model invocations for validation/logging
    - wrap_tool_call: wraps tool invocations for validation/logging

    All hooks are optional. Middleware implements only the hooks it needs.
    """

    async def before_agent(self, state: AgentRunState, context: HarnessContext) -> AgentRunState:
        """Run before the agent loop starts.

        Args:
            state: Current agent run state.
            context: Runtime context for this invocation.

        Returns:
            Possibly modified state.
        """
        return state

    async def after_agent(self, state: AgentRunState, context: HarnessContext) -> AgentRunState:
        """Run after the agent loop completes.

        Args:
            state: Current agent run state.
            context: Runtime context for this invocation.

        Returns:
            Possibly modified state.
        """
        return state

    async def before_model(self, state: AgentRunState, context: HarnessContext) -> AgentRunState:
        """Run before each model invocation.

        Args:
            state: Current agent run state.
            context: Runtime context for this invocation.

        Returns:
            Possibly modified state.
        """
        return state

    async def after_model(self, state: AgentRunState, context: HarnessContext) -> AgentRunState:
        """Run after each model invocation.

        Args:
            state: Current agent run state.
            context: Runtime context for this invocation.

        Returns:
            Possibly modified state.
        """
        return state

    async def wrap_model_call(
        self,
        state: AgentRunState,
        context: HarnessContext,
        call: Callable[[], Awaitable[Any]],
    ) -> Any:
        """Wrap a model invocation.

        Args:
            state: Current agent run state.
            context: Runtime context for this invocation.
            call: Callable that performs the actual model invocation.

        Returns:
            Result of the model call.
        """
        return await call()

    async def wrap_tool_call(
        self,
        state: AgentRunState,
        context: HarnessContext,
        tool_name: str,
        tool_args: dict[str, Any],
        call: Callable[[], Awaitable[Any]],
    ) -> Any:
        """Wrap a tool invocation.

        Args:
            state: Current agent run state.
            context: Runtime context for this invocation.
            tool_name: Name of the tool being invoked.
            tool_args: Arguments passed to the tool.
            call: Callable that performs the actual tool invocation.

        Returns:
            Result of the tool call.
        """
        return await call()
