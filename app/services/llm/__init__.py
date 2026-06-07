"""LLM package stub.

Phase 3: real LLM calls are disabled.  The harness uses FakeModel.
This stub preserves the import path for backward compatibility.
"""

from __future__ import annotations

from typing import Any


class LLMRegistry:
    """Stub — see app/agent_harness/models/ for the real model layer."""

    @staticmethod
    def get_all_names() -> list[str]:
        """Return list of available model names (stub returns fake-model)."""
        return ["fake-model"]

    @staticmethod
    def get(name: str, **kwargs: Any) -> Any:
        """Get model by name (stub returns None)."""
        return None


class LLMService:
    """Stub LLM service that raises on call.

    Phase 3: no real LLM calls.  Use harness FakeModel instead.
    """

    def __init__(self) -> None:
        """Initialize stub."""

    async def call(self, *args: Any, **kwargs: Any) -> Any:
        """Call the LLM (disabled in Phase 3, raises RuntimeError)."""
        raise RuntimeError("LLM calls are disabled in Phase 3. Use harness FakeModel.")

    def get_llm(self) -> Any:
        """Get the current LLM instance (stub returns None)."""
        return None

    def bind_tools(self, tools: list) -> "LLMService":
        """Bind tools to the LLM (stub returns self)."""
        return self


llm_service = LLMService()

__all__ = ["LLMRegistry", "LLMService", "llm_service"]
