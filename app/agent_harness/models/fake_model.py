"""FakeModel — deterministic, fixture-driven model response provider.

No real LLM calls.  Returns configurable deterministic responses based on
the input message text or a fixture registry.  Used in tests and Phase 3
default path.
"""

from __future__ import annotations

from app.agent_harness.contracts import AgentRunState, HarnessContext

# Default fixture responses keyed by trigger word
DEFAULT_FIXTURES: dict[str, str] = {
    "hello": "Hello! How can I help you today?",
    "help": "I'm a support assistant. I can help you with documentation, troubleshooting, and FAQs.",
    "bye": "Goodbye! Feel free to come back anytime.",
    "faq": "Here are some frequently asked questions about our platform...",
}


class FakeModel:
    """Deterministic fake model for testing and Phase 3 default path.

    Attributes:
        call_count: Number of times ``generate()`` was called.
        fixtures: Dict of trigger -> response text.
        default_response: Fallback response when no trigger matches.
    """

    def __init__(
        self,
        fixtures: dict[str, str] | None = None,
        default_response: str = "This is a fake model response.",
    ) -> None:
        """Initialize with fixture responses.

        Args:
            fixtures: Dict of trigger text -> response text.
                If None, uses ``DEFAULT_FIXTURES``.
            default_response: Fallback response when no trigger matches.
        """
        self.call_count = 0
        self.fixtures = fixtures or dict(DEFAULT_FIXTURES)
        self.default_response = default_response

    async def generate(
        self,
        state: AgentRunState,
        context: HarnessContext,
    ) -> str:
        """Generate a deterministic response based on input text.

        Args:
            state: Current agent run state (messages are inspected).
            context: Per-run harness context.

        Returns:
            Deterministic response string from fixtures or default.
        """
        self.call_count += 1

        messages = state.get("messages", [])
        # Find the last user message content
        last_user_text = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user_text = msg.get("content", "")
                break

        # Match against fixture triggers
        text_lower = last_user_text.lower()
        for trigger, response in self.fixtures.items():
            if trigger in text_lower:
                # Record model call metadata
                model_calls = state.get("model_calls_made", [])
                model_calls.append(
                    {
                        "provider": "fake",
                        "model": "fake-model",
                        "trigger": trigger,
                        "call_number": self.call_count,
                    }
                )
                state["model_calls_made"] = model_calls
                return response

        # Record default call
        model_calls = state.get("model_calls_made", [])
        model_calls.append(
            {
                "provider": "fake",
                "model": "fake-model",
                "trigger": "default",
                "call_number": self.call_count,
            }
        )
        state["model_calls_made"] = model_calls
        return self.default_response

    def reset(self) -> None:
        """Reset call count to zero."""
        self.call_count = 0
