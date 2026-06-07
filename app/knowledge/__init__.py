"""Knowledge retrieval contracts, query rewriting, and cache utilities.

Provides the ``QueryRewriter`` protocol and a deterministic rewriter
implementation, plus cache-key helpers for both embedding and retrieval
caches, retrieval-orchestration types, and the reranker contract.
"""

from app.knowledge.cache import (
    build_embedding_cache_key,
    build_retrieval_cache_key,
)
from app.knowledge.contracts import QueryRewriter
from app.knowledge.query_rewrite import DeterministicQueryRewriter
from app.knowledge.rerank import RerankedResult, Reranker
from app.knowledge.retrieval import ReciprocalRankFusionHybridRetriever
from app.vector.contracts import HybridRetriever
from app.vector.models import RetrievalMode, RetrievalQuery

__all__ = [
    "QueryRewriter",
    "DeterministicQueryRewriter",
    "build_embedding_cache_key",
    "build_retrieval_cache_key",
    "HybridRetriever",
    "ReciprocalRankFusionHybridRetriever",
    "RetrievalMode",
    "RetrievalQuery",
    "Reranker",
    "RerankedResult",
]
