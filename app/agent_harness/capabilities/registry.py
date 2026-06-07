"""FakeCapabilityRegistry — exposes only tenant-allowed capabilities."""

from __future__ import annotations

from typing import Any

from app.agent_harness.capabilities.rag_search import RagSearchCapability
from app.agent_harness.contracts import AgentRunState, HarnessContext
from app.knowledge.retrieval import ReciprocalRankFusionHybridRetriever
from app.vector.fake import FakeEmbeddingProvider, FakeKeywordSearchProvider, FakeVectorSearchProvider


class FakeCapabilityRegistry:
    """Exposes only tenant-allowed capabilities based on profile.

    Phase 3: simple dict-based registry with fixture implementations.
    Full capability manifest loading arrives in Phase 4.
    """

    def __init__(self, rag_search: RagSearchCapability | None = None) -> None:
        """Initialize with a hardcoded capability map."""
        default_rag = RagSearchCapability(
            ReciprocalRankFusionHybridRetriever(FakeVectorSearchProvider(), FakeKeywordSearchProvider()),
            FakeEmbeddingProvider(dimension=16),
        )
        self._capabilities: dict[str, Any] = {
            "fake_search": self._fake_search,
            "rag.search": rag_search or default_rag,
            "official_links": self._official_links,
            "disallowed_tool": self._disallowed_tool,
        }

    async def execute(
        self,
        state: AgentRunState,
        context: HarnessContext,
        name: str,
        args: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a capability by name, checking tenant allowlist.

        Args:
            state: Current agent run state.
            context: Per-run harness context.
            name: Capability name to execute.
            args: Arguments for the capability.

        Returns:
            Capability result dict.

        Raises:
            ValueError: If capability is not found.
        """
        allowed = state.get("available_capabilities", [])
        if name not in allowed:
            return {"error": f"Capability '{name}' not allowed", "denied": True}

        if name not in self._capabilities:
            return {"error": f"Capability '{name}' not found in registry", "denied": True}

        callable_fn = self._capabilities[name]
        if isinstance(callable_fn, RagSearchCapability):
            result = await callable_fn(args, tenant_id=context.get("tenant_id"))
        else:
            result = await callable_fn(args)

        # Record tool call
        tool_calls = state.get("tool_results", [])
        tool_calls.append(
            {
                "capability": name,
                "args": args,
                "result": result,
            }
        )
        state["tool_results"] = tool_calls
        return result

    def _list_available(self, allowed: list[str]) -> list[str]:
        """Return intersection of registered and allowed capability names."""
        return [name for name in self._capabilities if name in allowed]

    async def _fake_search(self, args: dict[str, Any]) -> dict[str, Any]:
        """Fake RAG search returning fixture data."""
        query = args.get("query", "")
        return {
            "source": "fake_rag",
            "query": query,
            "results": [
                {"title": "Fixture Result 1", "snippet": f"Fixture answer for: {query}", "score": 0.95},
                {"title": "Fixture Result 2", "snippet": "Additional fixture context.", "score": 0.80},
            ],
        }

    async def _official_links(self, args: dict[str, Any]) -> dict[str, Any]:
        """Return fixture official links."""
        return {
            "links": [
                {"title": "Documentation", "url": "https://docs.example.com"},
                {"title": "FAQ", "url": "https://faq.example.com"},
            ]
        }

    async def _disallowed_tool(self, args: dict[str, Any]) -> dict[str, Any]:
        """This tool should never be executed — it's not in allowed_capabilities."""
        raise RuntimeError("Disallowed tool was executed — this should never happen")
