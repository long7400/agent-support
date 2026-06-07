"""Abstract contracts for the knowledge-retrieval layer.

These protocols live in the ``app.knowledge`` package because they
operate at the query/text level rather than the vector-index level.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class QueryRewriter(Protocol):
    """Transforms a raw user query into an optimised search string.

    Implementations should be deterministic so that cache keys derived
    from the rewritten query are stable across calls.
    """

    def rewrite(self, query_text: str) -> str:
        """Rewrite a raw query text for improved retrieval.

        Args:
            query_text: Raw user query.

        Returns:
            Rewritten query string optimised for the downstream
            retrieval pipeline.
        """
        ...
