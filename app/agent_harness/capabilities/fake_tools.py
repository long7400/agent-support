"""Standalone fake tool implementations for testing.

These are independent functions (not methods on a class) so they can be
used directly in tests and integrated easily with the runner.
"""

from __future__ import annotations


async def fake_rag_search(query: str, top_k: int = 3) -> dict:
    """Fake RAG search returning deterministic fixture data.

    Args:
        query: Search query string.
        top_k: Maximum number of results (fixture always returns 2 regardless).

    Returns:
        Dict with results list.
    """
    return {
        "status": "ok",
        "source": "fake_rag",
        "query": query,
        "results": [
            {"title": "Fixture Result 1", "snippet": f"Fixture answer for: {query}", "relevance": 0.95},
            {"title": "Fixture Result 2", "snippet": "Additional fixture context.", "relevance": 0.80},
        ],
    }


async def fake_disabled_tool(tool_name: str) -> dict:
    """A tool that always returns a denial.

    This simulates a denied tool call — the tool body itself should never
    be reached if middleware correctly blocks it.

    Returns:
        Dict with denial result.
    """
    return {
        "status": "denied",
        "tool": tool_name,
        "reason": "Tool execution attempted despite policy denial (logic error)",
        "executed": True,  # Set to True to detect if this was accidentally called
    }
