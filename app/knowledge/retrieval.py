"""Retrieval orchestration types — query model, mode enum, hybrid retriever.

These types live in the ``app.knowledge`` package because they describe
*how* to retrieve from the knowledge base (orchestration), not the
low-level vector operations.
"""

from app.vector.contracts import HybridRetriever
from app.vector.models import RetrievalMode, RetrievalQuery

__all__ = [
    "HybridRetriever",
    "RetrievalMode",
    "RetrievalQuery",
]
