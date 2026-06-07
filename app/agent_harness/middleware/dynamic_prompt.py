"""Dynamic prompt middleware — assembles prompt from tenant/platform/memory fixtures."""

from __future__ import annotations

from typing import Any

from app.agent_harness.contracts import AgentRunState, HarnessContext


class DynamicPromptMiddleware:
    """Assemble system/developer context from tenant persona, policy, locale, retrieved memory, source rules.

    This middleware runs in before_model and:
    - Builds a system prompt from tenant persona (from profile)
    - Adds platform-specific formatting instructions
    - Includes memory context (from memory middleware)
    - Includes policy constraints

    Phase 3 uses fake/fixtures for all prompt components.
    """

    def __init__(self, prompt_builder: Any = None) -> None:
        """Initialize with optional prompt builder.

        Args:
            prompt_builder: Callable that builds prompt from context.
                If None, uses default fake prompt builder.
        """
        self._prompt_builder = prompt_builder or self._default_prompt_builder

    async def _default_prompt_builder(
        self,
        tenant_context: dict[str, Any],
        platform_context: dict[str, Any],
        memory_context: dict[str, Any],
    ) -> str:
        """Default fake prompt builder for Phase 3."""
        parts = []
        parts.append("You are a helpful support agent.")

        # Add tenant persona if available
        persona = tenant_context.get("persona", {})
        if persona.get("name"):
            parts.append(f"You represent {persona['name']}.")

        # Add platform formatting hint
        formatting = platform_context.get("formatting", "plain")
        if formatting == "markdown_html":
            parts.append("Use Markdown or HTML formatting as appropriate.")
        elif formatting == "markdown":
            parts.append("Use Markdown formatting.")

        # Add memory context if available
        if memory_context.get("summary"):
            parts.append(f"\nContext: {memory_context['summary']}")

        return "\n".join(parts)

    async def before_model(self, state: AgentRunState, context: HarnessContext) -> AgentRunState:
        """Build system prompt and inject into state."""
        tenant_context = state.get("tenant_context", {})
        platform_context = state.get("platform_context", {})
        memory_context = state.get("memory_context", {})

        system_prompt = await self._prompt_builder(tenant_context, platform_context, memory_context)

        # Inject system prompt into messages
        messages = list(state.get("messages", []))

        # Remove any existing system message
        messages = [m for m in messages if m.get("role") != "system"]

        # Add system prompt at the beginning
        system_message = {"role": "system", "content": system_prompt}
        messages.insert(0, system_message)

        state["messages"] = messages

        return state
