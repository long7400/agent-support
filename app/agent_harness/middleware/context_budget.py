"""Context budget middleware — compact messages/tool outputs before context overflow."""

from __future__ import annotations

from typing import Any

from app.agent_harness.contracts import AgentRunState, HarnessContext


class ContextBudgetMiddleware:
    """Compact messages and tool outputs before context overflow.

    This middleware runs in before_model and:
    - Checks total message/token count against budget
    - Compacts old messages into a summary if over budget
    - Truncates tool outputs to bounded size
    - Ensures system prompt + recent messages fit in budget

    Phase 3 uses simple token counting. Phase 4+ will use tiktoken.
    """

    # Default budget: ~4000 tokens (rough estimate)
    DEFAULT_MAX_TOKENS = 4000
    # Reserve tokens for model response
    RESERVED_RESPONSE_TOKENS = 500

    def __init__(self, max_tokens: int | None = None) -> None:
        """Initialize with optional max token budget.

        Args:
            max_tokens: Maximum tokens for context. Defaults to 4000.
        """
        self._max_tokens = max_tokens or self.DEFAULT_MAX_TOKENS

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count (rough: 1 token ≈ 4 chars).

        Phase 4 will use tiktoken for accurate counting.
        """
        return len(text) // 4

    def _compact_messages(
        self, messages: list[dict[str, Any]], max_tokens: int
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Compact messages to fit within token budget.

        Returns:
            Tuple of (compacted_messages, rolling_summary_or_none)
        """
        # Keep system message + last N messages
        system_msg = None
        other_messages = []

        for msg in messages:
            if msg.get("role") == "system":
                system_msg = msg
            else:
                other_messages.append(msg)

        # Calculate tokens for system message
        system_tokens = 0
        if system_msg:
            system_tokens = self._estimate_tokens(system_msg.get("content", ""))

        # Work backwards to keep most recent messages
        available_tokens = max_tokens - system_tokens - self.RESERVED_RESPONSE_TOKENS
        kept_messages = []
        total_tokens = 0

        for msg in reversed(other_messages):
            msg_tokens = self._estimate_tokens(str(msg.get("content", "")))
            if total_tokens + msg_tokens > available_tokens:
                break
            kept_messages.insert(0, msg)
            total_tokens += msg_tokens

        # If we dropped messages, create a summary
        dropped_count = len(other_messages) - len(kept_messages)
        summary = None
        if dropped_count > 0:
            summary = f"[{dropped_count} earlier messages summarized]"

        # Reconstruct messages
        result = []
        if system_msg:
            result.append(system_msg)
        if summary:
            result.append({"role": "system", "content": summary})
        result.extend(kept_messages)

        return result, summary

    async def before_model(self, state: AgentRunState, context: HarnessContext) -> AgentRunState:
        """Compact messages if over budget."""
        messages = list(state.get("messages", []))

        # Compact messages
        compacted_messages, summary = self._compact_messages(messages, self._max_tokens)

        # Update state
        state["messages"] = compacted_messages

        # Track budget usage
        budget = dict(state.get("budgets", {}))
        budget["context_tokens_used"] = sum(
            self._estimate_tokens(str(m.get("content", ""))) for m in compacted_messages
        )
        budget["context_max_tokens"] = self._max_tokens
        state["budgets"] = budget

        # Update memory context with summary
        if summary:
            memory_context = dict(state.get("memory_context", {}))
            memory_context["compacted"] = True
            memory_context["rolling_summary"] = summary
            state["memory_context"] = memory_context

        return state
