"""Memory middleware — loads checkpoint-backed short-term memory (fake fixtures for P3)."""

from __future__ import annotations

from typing import Any

from app.agent_harness.contracts import AgentRunState, HarnessContext


class MemoryMiddleware:
    """Load checkpoint-backed short-term memory before run and write bounded useful facts after.

    Phase 3 uses fake fixtures for memory. Real memory (Qdrant, long-term) comes in Phase 4.

    This middleware:
    - before_agent: Loads short-term memory from checkpoint (or fake fixture)
    - after_agent: Writes bounded facts to memory (stub in Phase 3)

    Memory structure (Phase 3):
    - recent_messages: Recent conversation history
    - rolling_summary: Bounded summary of conversation
    - tool_refs: References to recent tool results
    - token_budget_used: Tokens used in memory context
    """

    def __init__(self, memory_loader: Any = None) -> None:
        """Initialize with optional memory loader.

        Args:
            memory_loader: Callable that loads memory for a thread.
                If None, uses default fake memory.
        """
        self._memory_loader = memory_loader or self._default_memory_loader

    async def _default_memory_loader(self, thread_id: str | None, tenant_id: Any) -> dict[str, Any]:
        """Default fake memory loader for Phase 3."""
        # In Phase 3, return empty fake memory
        # Phase 4 will load from checkpoint/DB
        return {
            "recent_messages": [],
            "rolling_summary": None,
            "tool_refs": [],
            "token_budget_used": 0,
        }

    async def before_agent(self, state: AgentRunState, context: HarnessContext) -> AgentRunState:
        """Load short-term memory into state."""
        thread_id = state.get("thread_id")
        tenant_id = state.get("tenant_id")

        memory = await self._memory_loader(thread_id, tenant_id)

        # Store memory in state
        state["memory_context"] = {
            "recent_messages": memory.get("recent_messages", []),
            "rolling_summary": memory.get("rolling_summary"),
            "tool_refs": memory.get("tool_refs", []),
            "token_budget_used": memory.get("token_budget_used", 0),
            "loaded": True,
        }

        return state

    async def after_agent(self, state: AgentRunState, context: HarnessContext) -> AgentRunState:
        """Write bounded facts to memory (stub in Phase 3).

        Phase 4 will implement actual memory persistence.
        """
        # In Phase 3, this is a no-op
        # Phase 4 will:
        # - Extract useful facts from the run
        # - Apply sensitivity/consent filters
        # - Write to long-term memory with TTL
        # - Update rolling summary if needed

        # Record that memory write was attempted
        memory_context = state.get("memory_context", {})
        memory_context["write_attempted"] = False  # Phase 3 doesn't write
        state["memory_context"] = memory_context

        return state
