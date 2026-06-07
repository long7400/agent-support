"""Reranker contract for post-retrieval relevance scoring.

The reranker lives in the ``app.knowledge`` package because it operates
on retrieved results (knowledge) and sits between retrieval and the
downstream answer generation.
"""

from app.vector.contracts import RerankedResult, Reranker

__all__ = [
    "Reranker",
    "RerankedResult",
]
