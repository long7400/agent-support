"""Abstract contracts for the vector / retrieval layer.

All provider interfaces are defined as :class:`~typing.Protocol` so that
concrete implementations can be substituted without class inheritance.
Result types are lightweight dataclasses.

Every ``search``-like method **MUST** reject or return empty when
``tenant_id`` is ``None`` or zero / empty (fail-closed).  This is the
primary tenant isolation invariant for the retrieval layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable
from uuid import UUID


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VectorResult:
    """A single hit from a vector (dense) search."""

    chunk_id: UUID
    score: float
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class KeywordResult:
    """A single hit from a keyword (lexical) search."""

    chunk_id: UUID
    score: float
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RerankedResult:
    """A single candidate after reranking with its final rank."""

    chunk_id: UUID
    score: float
    rank: int
    payload: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Provider protocols
# ---------------------------------------------------------------------------


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Produces vector embeddings from text input.

    Implementations must be deterministic or at least idempotent for the
    same input so that cache keys remain valid.
    """

    async def embed(self, texts: list[str], tenant_id: UUID) -> list[list[float]]:
        """Embed one or more text strings.

        Args:
            texts: List of text strings to embed.
            tenant_id: Tenant scope (MUST NOT be None/empty).

        Returns:
            List of embedding vectors, one per input text.

        Raises:
            ValueError: If ``tenant_id`` is None or zero.
        """
        ...

    async def embed_query(self, text: str, tenant_id: UUID) -> list[float]:
        """Embed a single query string (may use a different instruction).

        Args:
            text: Query text to embed.
            tenant_id: Tenant scope (MUST NOT be None/empty).

        Returns:
            A single embedding vector.

        Raises:
            ValueError: If ``tenant_id`` is None or zero.
        """
        ...


@runtime_checkable
class VectorSearchProvider(Protocol):
    """Dense vector similarity search against indexed embeddings.

    **Tenant isolation:** every ``search`` call MUST reject
    ``None``/``empty`` ``tenant_id`` values.  Qdrant does not have RLS,
    so this invariant is enforced at the application layer.
    """

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
        """Execute a dense vector search.

        Args:
            query_embedding: The query vector.
            tenant_id: **Mandatory** tenant scope.
            candidate_top_k: Max raw candidates to retrieve.
            visibility: Allowed visibility levels.
            source_allowlist: Optional source UUID filter.
            locale: Optional locale filter.
            active_only: Only return active (non-tombstoned) chunks.
            source_version_ids: Optional source-version UUID filter.

        Returns:
            List of ``VectorResult`` hits, ordered by descending score.

        Raises:
            ValueError: If ``tenant_id`` is None or zero.
        """
        ...


@runtime_checkable
class KeywordSearchProvider(Protocol):
    """Lexical (keyword) search against indexed chunk text.

    **Tenant isolation:** every ``search`` call MUST reject
    ``None``/``empty`` ``tenant_id`` values.
    """

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
        """Execute a lexical keyword search.

        Args:
            query_text: Raw query text.
            tenant_id: **Mandatory** tenant scope.
            candidate_top_k: Max raw candidates to retrieve.
            visibility: Allowed visibility levels.
            source_allowlist: Optional source UUID filter.
            locale: Optional locale filter.
            active_only: Only return active (non-tombstoned) chunks.
            source_version_ids: Optional source-version UUID filter.

        Returns:
            List of ``KeywordResult`` hits, ordered by descending score.

        Raises:
            ValueError: If ``tenant_id`` is None or zero.
        """
        ...


@runtime_checkable
class HybridRetriever(Protocol):
    """Combines dense (vector) and lexical (keyword) results.

    Candidates are deduplicated by ``chunk_id`` and fused via
    Reciprocal Rank Fusion (RRF) scoring.
    """

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
        """Execute a hybrid (dense + lexical) search with RRF fusion.

        Args:
            query_text: Raw text for the keyword branch.
            query_embedding: Query vector for the dense branch.
            tenant_id: **Mandatory** tenant scope.
            candidate_top_k: Raw candidates per branch before fusion.
            final_top_k: Results to return after fusion.
            visibility: Allowed visibility levels.
            source_allowlist: Optional source UUID filter.
            locale: Optional locale filter.
            active_only: Only return active (non-tombstoned) chunks.
            source_version_ids: Optional source-version UUID filter.

        Returns:
            List of ``VectorResult`` hits fused by RRF, ordered by
            descending fused score.

        Raises:
            ValueError: If ``tenant_id`` is None or zero.
        """
        ...


@runtime_checkable
class Reranker(Protocol):
    """Reranks an initial set of candidates for better relevance."""

    async def rerank(
        self,
        query: str,
        candidates: list[VectorResult],
        top_k: int = 10,
    ) -> list[RerankedResult]:
        """Rerank candidates by relevance to the query.

        Args:
            query: The original user query text.
            candidates: Initial ranked candidates.
            top_k: Max number of results to return.

        Returns:
            Re-ranked results with updated scores and final rank
            positions.
        """
        ...
