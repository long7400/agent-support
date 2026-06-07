"""Hybrid retrieval orchestration."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.vector.contracts import KeywordSearchProvider, VectorResult, VectorSearchProvider

_RRF_K = 60


class ReciprocalRankFusionHybridRetriever:
    """Fuse dense and lexical candidates using Reciprocal Rank Fusion."""

    def __init__(self, vector_provider: VectorSearchProvider, keyword_provider: KeywordSearchProvider) -> None:
        """Initialize with dense and lexical providers."""
        self._vector_provider = vector_provider
        self._keyword_provider = keyword_provider

    async def search(
        self,
        query_text: str,
        query_embedding: list[float],
        tenant_id: UUID,
        candidate_top_k: int = 50,
        final_top_k: int = 10,
        visibility: list[str] | None = None,
        source_allowlist: list[UUID] | None = None,
        locale: str | None = None,
        active_only: bool = True,
        source_version_ids: list[UUID] | None = None,
    ) -> list[VectorResult]:
        """Run dense and lexical searches, then return fused results."""
        if tenant_id is None or tenant_id == UUID(int=0):
            raise ValueError("tenant_id must not be None or zero")
        bounded_final_top_k = max(1, min(final_top_k, 10))
        vector_results = await self._vector_provider.search(
            query_embedding=query_embedding,
            tenant_id=tenant_id,
            candidate_top_k=candidate_top_k,
            visibility=visibility,
            source_allowlist=source_allowlist,
            locale=locale,
            active_only=active_only,
            source_version_ids=source_version_ids,
        )
        keyword_results = await self._keyword_provider.search(
            query_text=query_text,
            tenant_id=tenant_id,
            candidate_top_k=candidate_top_k,
            visibility=visibility,
            source_allowlist=source_allowlist,
            locale=locale,
            active_only=active_only,
            source_version_ids=source_version_ids,
        )
        fused: dict[UUID, tuple[float, dict[str, Any]]] = {}
        for rank, result in enumerate(vector_results, start=1):
            score, payload = fused.get(result.chunk_id, (0.0, result.payload))
            fused[result.chunk_id] = (score + _rrf(rank), {**payload, "vector_score": result.score})
        for rank, result in enumerate(keyword_results, start=1):
            score, payload = fused.get(result.chunk_id, (0.0, result.payload))
            fused[result.chunk_id] = (score + _rrf(rank), {**payload, "keyword_score": result.score})
        ordered = sorted(fused.items(), key=lambda item: item[1][0], reverse=True)
        return [VectorResult(chunk_id=chunk_id, score=score, payload=payload) for chunk_id, (score, payload) in ordered[:bounded_final_top_k]]


def _rrf(rank: int) -> float:
    return 1.0 / (_RRF_K + rank)
