"""Vector search and retrieval contracts, models, and fake providers.

Phase 4 implementation provides ABC/Protocol interfaces for embedding,
vector search, keyword search, hybrid retrieval, and reranking.  Fake
deterministic providers enable unit testing without Qdrant or network.
"""

from app.vector.contracts import (
    EmbeddingProvider,
    HybridRetriever,
    KeywordResult,
    KeywordSearchProvider,
    RerankedResult,
    Reranker,
    VectorResult,
    VectorSearchProvider,
)
from app.vector.fake import (
    FakeEmbeddingProvider,
    FakeHybridRetriever,
    FakeKeywordSearchProvider,
    FakeReranker,
    FakeVectorSearchProvider,
)
from app.vector.models import RetrievalMode, RetrievalQuery

__all__ = [
    "EmbeddingProvider",
    "HybridRetriever",
    "KeywordResult",
    "KeywordSearchProvider",
    "RerankedResult",
    "Reranker",
    "VectorResult",
    "VectorSearchProvider",
    "FakeEmbeddingProvider",
    "FakeHybridRetriever",
    "FakeKeywordSearchProvider",
    "FakeReranker",
    "FakeVectorSearchProvider",
    "RetrievalMode",
    "RetrievalQuery",
]
