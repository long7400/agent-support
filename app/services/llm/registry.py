"""LLM registry stub.

Phase 3: no real LLM calls.  This file exists for import compatibility.
"""

from __future__ import annotations

from typing import Any


class LLMRegistry:
    """Stub registry for backward compatibility."""

    LLMS: list[dict[str, Any]] = []

    @staticmethod
    def get_all_names() -> list[str]:
        """Return list of available model names (stub returns fake-model)."""
        return ["fake-model"]

    @staticmethod
    def get(name: str, **kwargs: Any) -> Any:
        """Get model by name (stub returns None)."""
        return None

    @staticmethod
    def get_model_at_index(index: int) -> dict[str, Any]:
        """Get model at index (stub returns fake-model)."""
        return {"name": "fake-model", "llm": None}
