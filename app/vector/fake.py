"""Fake deterministic providers for unit testing.

All implementations are in-memory, require no network, and enforce
tenant-id fail-closed behaviour at the application layer.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.vector.contracts import (
    KeywordResult,
    RerankedResult,
    VectorResult,
)

# ---------------------------------------------------------------------------
# Internal index types
# ---------------------------------------------------------------------------

_RRF_K = 60  # Reciprocal Rank Fusion constant


@dataclass
class _IndexedVector:
    """An indexed vector point with its metadata (fake analogue of a Qdrant point)."""

    chunk_id: UUID
    tenant_id: UUID
    embedding: list[float]
    text: str
    visibility: str
    locale: str | None
    is_active: bool
    source_version_id: UUID
    source_id: UUID
    payload: dict[str, Any]


@dataclass
class _IndexedKeyword:
    """An indexed keyword document (fake analogue of an inverted-index entry)."""

    chunk_id: UUID
    tenant_id: UUID
    text: str
    visibility: str
    locale: str | None
    is_active: bool
    source_version_id: UUID
    source_id: UUID
    payload: dict[str, Any]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_empty_tenant(tenant_id: UUID | None) -> bool:
    """Return True if tenant_id is None or the nil UUID."""
    return tenant_id is None or tenant_id == UUID(int=0)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between equal-dimension vectors."""
    if len(a) != len(b):
        raise ValueError("vector dimensions must match")
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _rrf_score(rank: int, k: int = _RRF_K) -> float:
    """Reciprocal Rank Fusion score for a single rank position."""
    return 1.0 / (k + rank)


# ---------------------------------------------------------------------------
# FakeEmbeddingProvider
# ---------------------------------------------------------------------------


class FakeEmbeddingProvider:
    """Deterministic embedding provider based on SHA-256 hashing.

    Same input text always produces the same embedding vector.
    No network calls are made.
    """

    def __init__(self, dimension: int = 384) -> None:
        """Initialise the fake provider.

        Args:
            dimension: Dimensionality of generated vectors.
        """
        self._dimension = dimension

    async def embed(self, texts: list[str], tenant_id: UUID) -> list[list[float]]:
        """Embed each text deterministically.

        Args:
            texts: Texts to embed.
            tenant_id: Tenant scope.

        Returns:
            List of embedding vectors.

        Raises:
            ValueError: If ``tenant_id`` is None or zero.
        """
        if _is_empty_tenant(tenant_id):
            raise ValueError("tenant_id must not be None or zero")
        return [self._deterministic_vector(t) for t in texts]

    async def embed_query(self, text: str, tenant_id: UUID) -> list[float]:
        """Embed a query string deterministically.

        Args:
            text: Query text.
            tenant_id: Tenant scope.

        Returns:
            Single embedding vector.

        Raises:
            ValueError: If ``tenant_id`` is None or zero.
        """
        if _is_empty_tenant(tenant_id):
            raise ValueError("tenant_id must not be None or zero")
        return self._deterministic_vector(text)

    def _deterministic_vector(self, text: str) -> list[float]:
        """Produce a fixed-dimension vector from repeated SHA-256 blocks."""
        out: list[float] = []
        block_index = 0
        while len(out) < self._dimension:
            digest = hashlib.sha256(f"{block_index}:{text}".encode("utf-8")).digest()
            out.extend(byte_val / 255.0 for byte_val in digest)
            block_index += 1
        return out[: self._dimension]


# ---------------------------------------------------------------------------
# FakeVectorSearchProvider
# ---------------------------------------------------------------------------


class FakeVectorSearchProvider:
    """In-memory vector search with deterministic cosine-similarity scoring.

    Accepts a pre-built index of ``_IndexedVector`` items at construction.
    All searches enforce tenant-id fail-closed semantics.
    """

    def __init__(self, index: list[_IndexedVector] | None = None) -> None:
        """Initialise with an optional pre-built index.

        Args:
            index: Items to search against.  An empty list is used if
                ``None``.
        """
        self._index: list[_IndexedVector] = list(index) if index is not None else []

    async def search(
        self,
        query_embedding: list[float],
        tenant_id: UUID,
        candidate_top_k: int = 50,
        visibility: list[str] | None = None,
        source_allowlist: list[UUID] | None = None,
        locale: str | None = None,
        active_only: bool = True,
        source_version_ids: list[UUID] | None = None,
    ) -> list[VectorResult]:
        """Search the in-memory index with tenant fail-closed."""
        if _is_empty_tenant(tenant_id):
            raise ValueError("tenant_id must not be None or zero")

        allowed_vis = set(visibility or ["public"])
        allowed_sv = set(source_version_ids) if source_version_ids else None
        allowed_src = set(source_allowlist) if source_allowlist else None

        candidates: list[VectorResult] = []
        for item in self._index:
            if item.tenant_id != tenant_id:
                continue
            if active_only and not item.is_active:
                continue
            if item.visibility not in allowed_vis:
                continue
            if allowed_sv is not None and item.source_version_id not in allowed_sv:
                continue
            if allowed_src is not None and item.source_id not in allowed_src:
                continue
            if locale is not None and item.locale != locale:
                continue

            score = _cosine_similarity(query_embedding, item.embedding)
            candidates.append(
                VectorResult(chunk_id=item.chunk_id, score=score, payload=item.payload)
            )

        candidates.sort(key=lambda r: r.score, reverse=True)
        return candidates[:candidate_top_k]


# ---------------------------------------------------------------------------
# FakeKeywordSearchProvider
# ---------------------------------------------------------------------------


class FakeKeywordSearchProvider:
    """In-memory keyword search using case-insensitive substring matching.

    Accepts a pre-built index of ``_IndexedKeyword`` items.
    All searches enforce tenant-id fail-closed semantics.
    """

    def __init__(self, index: list[_IndexedKeyword] | None = None) -> None:
        """Initialise with an optional pre-built index.

        Args:
            index: Items to search against.  An empty list is used if
                ``None``.
        """
        self._index: list[_IndexedKeyword] = list(index) if index is not None else []

    async def search(
        self,
        query_text: str,
        tenant_id: UUID,
        candidate_top_k: int = 50,
        visibility: list[str] | None = None,
        source_allowlist: list[UUID] | None = None,
        locale: str | None = None,
        active_only: bool = True,
        source_version_ids: list[UUID] | None = None,
    ) -> list[KeywordResult]:
        """Search the in-memory index with tenant fail-closed."""
        if _is_empty_tenant(tenant_id):
            raise ValueError("tenant_id must not be None or zero")

        query_lower = query_text.lower()
        allowed_vis = set(visibility or ["public"])
        allowed_sv = set(source_version_ids) if source_version_ids else None
        allowed_src = set(source_allowlist) if source_allowlist else None

        candidates: list[KeywordResult] = []
        for item in self._index:
            if item.tenant_id != tenant_id:
                continue
            if active_only and not item.is_active:
                continue
            if item.visibility not in allowed_vis:
                continue
            if allowed_sv is not None and item.source_version_id not in allowed_sv:
                continue
            if allowed_src is not None and item.source_id not in allowed_src:
                continue
            if locale is not None and item.locale != locale:
                continue

            text_lower = item.text.lower()
            if query_lower in text_lower:
                # Score = ratio of characters matched / total length (simple heuristic)
                score = len(query_lower) / max(len(text_lower), 1)
                candidates.append(
                    KeywordResult(chunk_id=item.chunk_id, score=score, payload=item.payload)
                )

        candidates.sort(key=lambda r: r.score, reverse=True)
        return candidates[:candidate_top_k]


# ---------------------------------------------------------------------------
# FakeHybridRetriever
# ---------------------------------------------------------------------------


class FakeHybridRetriever:
    """Hybrid retriever fusing dense and lexical candidates via RRF.

    Composes a ``FakeVectorSearchProvider`` and a
    ``FakeKeywordSearchProvider`` internally.  Candidates are deduplicated
    by ``chunk_id`` and scored with Reciprocal Rank Fusion.
    """

    def __init__(
        self,
        vector_provider: FakeVectorSearchProvider,
        keyword_provider: FakeKeywordSearchProvider,
    ) -> None:
        """Initialise with concrete fake provider instances.

        Args:
            vector_provider: Dense search provider.
            keyword_provider: Lexical search provider.
        """
        self._vector = vector_provider
        self._keyword = keyword_provider

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
        """Execute a hybrid search with RRF fusion and tenant fail-closed."""
        if _is_empty_tenant(tenant_id):
            raise ValueError("tenant_id must not be None or zero")

        vector_results = await self._vector.search(
            query_embedding=query_embedding,
            tenant_id=tenant_id,
            candidate_top_k=candidate_top_k,
            visibility=visibility,
            source_allowlist=source_allowlist,
            locale=locale,
            active_only=active_only,
            source_version_ids=source_version_ids,
        )
        keyword_results = await self._keyword.search(
            query_text=query_text,
            tenant_id=tenant_id,
            candidate_top_k=candidate_top_k,
            visibility=visibility,
            source_allowlist=source_allowlist,
            locale=locale,
            active_only=active_only,
            source_version_ids=source_version_ids,
        )

        # RRF fusion with dedup by chunk_id
        rrf_scores: dict[UUID, tuple[float, dict[str, Any]]] = {}

        for rank, hit in enumerate(vector_results):
            score = _rrf_score(rank)
            if hit.chunk_id in rrf_scores:
                existing_score, payload = rrf_scores[hit.chunk_id]
                rrf_scores[hit.chunk_id] = (existing_score + score, payload)
            else:
                rrf_scores[hit.chunk_id] = (score, hit.payload)

        for rank, hit in enumerate(keyword_results):
            score = _rrf_score(rank)
            if hit.chunk_id in rrf_scores:
                existing_score, payload = rrf_scores[hit.chunk_id]
                rrf_scores[hit.chunk_id] = (existing_score + score, payload)
            else:
                rrf_scores[hit.chunk_id] = (score, hit.payload)

        # Sort by fused score descending
        sorted_chunks = sorted(rrf_scores.items(), key=lambda kv: kv[1][0], reverse=True)
        return [
            VectorResult(chunk_id=cid, score=sc, payload=pld)
            for cid, (sc, pld) in sorted_chunks[:final_top_k]
        ]


# ---------------------------------------------------------------------------
# FakeReranker
# ---------------------------------------------------------------------------


class FakeReranker:
    """Dummy reranker that filters by a minimum score threshold.

    Acts as a pass-through with a configurable ``min_score``.  Candidates
    below the threshold are dropped; the remainder keep their original
    score but receive a new rank position.
    """

    def __init__(self, min_score: float = 0.0) -> None:
        """Initialise with a minimum score threshold.

        Args:
            min_score: Minimum score for a candidate to pass the filter.
        """
        self._min_score = min_score

    async def rerank(
        self,
        query: str,
        candidates: list[VectorResult],
        top_k: int = 10,
    ) -> list[RerankedResult]:
        """Filter candidates by score threshold and assign ranks.

        Args:
            query: Original user query (unused in this fake).
            candidates: Initial candidates.
            top_k: Max results to return after filtering.

        Returns:
            Filtered and ranked results.
        """
        filtered = [c for c in candidates if c.score >= self._min_score]
        filtered.sort(key=lambda r: r.score, reverse=True)
        return [
            RerankedResult(chunk_id=c.chunk_id, score=c.score, rank=i, payload=c.payload)
            for i, c in enumerate(filtered[:top_k])
        ]
