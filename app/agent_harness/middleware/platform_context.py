"""Platform context middleware — applies platform-specific constraints."""

from __future__ import annotations

from app.agent_harness.contracts import AgentRunState, HarnessContext


class PlatformContextMiddleware:
    """Apply Telegram/Discord response limits and formatting constraints.

    This middleware runs in before_agent and:
    - Detects the platform from the inbound event
    - Applies platform-specific response limits (message length, formatting)
    - Records platform constraints in state for downstream middleware

    Platform limits (Phase 3 skeleton):
    - Telegram: 4096 chars per message, Markdown/HTML formatting
    - Discord: 2000 chars per message, Markdown formatting
    """

    # Platform-specific limits
    PLATFORM_LIMITS = {
        "telegram": {
            "max_message_length": 4096,
            "max_messages": 10,
            "formatting": "markdown_html",
        },
        "discord": {
            "max_message_length": 2000,
            "max_messages": 10,
            "formatting": "markdown",
        },
    }

    async def before_agent(self, state: AgentRunState, context: HarnessContext) -> AgentRunState:
        """Apply platform-specific constraints to state."""
        platform = state.get("platform", "telegram")
        limits = self.PLATFORM_LIMITS.get(platform, self.PLATFORM_LIMITS["telegram"])

        # Store platform context for downstream middleware
        state["platform_context"] = {
            "platform": platform,
            "max_message_length": limits["max_message_length"],
            "max_messages": limits["max_messages"],
            "formatting": limits["formatting"],
            "channel_id": state.get("channel_id", ""),
            "thread_id": state.get("thread_id"),
        }

        return state
