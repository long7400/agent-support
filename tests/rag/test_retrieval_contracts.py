"""Tests for retrieval contracts, fake providers, and tenant isolation."""

from uuid import UUID, uuid4

import pytest

from app.vector.contracts import (
    EmbeddingProvider,
    HybridRetriever,
    KeywordSearchProvider,
    VectorResult,
    VectorSearchProvider,
)
from app.vector.fake import (
    FakeEmbeddingProvider,
    FakeHybridRetriever,
    FakeKeywordSearchProvider,
    FakeReranker,
    FakeVectorSearchProvider,
    _IndexedKeyword,
    _IndexedVector,
)
from app.vector.models import RetrievalMode, RetrievalQuery

# ── helpers ────────────────────────────────────────────────────────────


def _make_vector(
    chunk_id: UUID | None = None,
    tenant_id: UUID | None = None,
    text: str = "hello world",
    visibility: str = "public",
    is_active: bool = True,
    locale: str | None = "en",
    source_version_id: UUID | None = None,
    source_id: UUID | None = None,
) -> _IndexedVector:
    """Build an ``_IndexedVector`` with reasonable defaults."""
    tid = tenant_id or uuid4()
    cid = chunk_id or uuid4()
    return _IndexedVector(
        chunk_id=cid,
        tenant_id=tid,
        embedding=[0.1, 0.2, 0.3],
        text=text,
        visibility=visibility,
        locale=locale,
        is_active=is_active,
        source_version_id=source_version_id or uuid4(),
        source_id=source_id or uuid4(),
        payload={"text": text},
    )


def _make_keyword_item(
    chunk_id: UUID | None = None,
    tenant_id: UUID | None = None,
    text: str = "hello world",
    visibility: str = "public",
    is_active: bool = True,
    locale: str | None = "en",
    source_version_id: UUID | None = None,
    source_id: UUID | None = None,
) -> _IndexedKeyword:
    """Build an ``_IndexedKeyword`` with reasonable defaults."""
    tid = tenant_id or uuid4()
    cid = chunk_id or uuid4()
    return _IndexedKeyword(
        chunk_id=cid,
        tenant_id=tid,
        text=text,
        visibility=visibility,
        locale=locale,
        is_active=is_active,
        source_version_id=source_version_id or uuid4(),
        source_id=source_id or uuid4(),
        payload={"text": text},
    )


# ── FakeEmbeddingProvider ──────────────────────────────────────────────


class TestFakeEmbeddingProvider:
    """Determinism, tenant fail-closed, and protocol conformance."""

    def test_embed_returns_deterministic_vectors(self) -> None:
        """Same input produces same output across calls."""
        provider = FakeEmbeddingProvider(dimension=4)
        tid = uuid4()

        result_a = asyncio_run(provider.embed(["hello"], tid))
        result_b = asyncio_run(provider.embed(["hello"], tid))

        assert result_a == result_b

    def test_embed_query_returns_deterministic_vector(self) -> None:
        """Same query input produces same output."""
        provider = FakeEmbeddingProvider(dimension=4)
        tid = uuid4()

        v1 = asyncio_run(provider.embed_query("hello", tid))
        v2 = asyncio_run(provider.embed_query("hello", tid))

        assert v1 == v2

    def test_embed_different_inputs_different_vectors(self) -> None:
        """Different inputs produce different vectors."""
        provider = FakeEmbeddingProvider(dimension=4)
        tid = uuid4()

        v1 = asyncio_run(provider.embed(["hello"], tid))[0]
        v2 = asyncio_run(provider.embed(["world"], tid))[0]

        assert v1 != v2

    def test_conforms_to_protocol(self) -> None:
        """FakeEmbeddingProvider satisfies the EmbeddingProvider protocol."""
        provider = FakeEmbeddingProvider()
        assert isinstance(provider, EmbeddingProvider)  # structural check

    @pytest.mark.parametrize("bad_tenant", [None, UUID(int=0)])
    def test_embed_raises_on_empty_tenant(self, bad_tenant: UUID | None) -> None:
        """Embed raises ValueError when tenant_id is None or zero."""
        provider = FakeEmbeddingProvider()
        with pytest.raises(ValueError, match="tenant_id"):
            asyncio_run(provider.embed(["hello"], bad_tenant))  # type: ignore[arg-type]

    @pytest.mark.parametrize("bad_tenant", [None, UUID(int=0)])
    def test_embed_query_raises_on_empty_tenant(self, bad_tenant: UUID | None) -> None:
        """embed_query raises ValueError when tenant_id is None or zero."""
        provider = FakeEmbeddingProvider()
        with pytest.raises(ValueError, match="tenant_id"):
            asyncio_run(provider.embed_query("hello", bad_tenant))  # type: ignore[arg-type]


# ── FakeVectorSearchProvider ───────────────────────────────────────────


class TestFakeVectorSearchProvider:
    """In-memory vector search, filtering, and tenant isolation."""

    def test_conforms_to_protocol(self) -> None:
        """FakeVectorSearchProvider satisfies the VectorSearchProvider protocol."""
        provider = FakeVectorSearchProvider()
        assert isinstance(provider, VectorSearchProvider)

    def test_returns_empty_when_no_match(self) -> None:
        """Search returns empty list when no items match."""
        provider = FakeVectorSearchProvider()
        result = asyncio_run(provider.search([0.1, 0.2, 0.3], tenant_id=uuid4()))
        assert result == []

    def test_returns_results_filtered_by_tenant(self) -> None:
        """Items from other tenants are not returned."""
        tid_a = uuid4()
        tid_b = uuid4()
        chunk = uuid4()
        index = [_make_vector(chunk_id=chunk, tenant_id=tid_a)]
        provider = FakeVectorSearchProvider(index)

        results = asyncio_run(provider.search([0.1, 0.2, 0.3], tenant_id=tid_b))
        assert results == []

    def test_returns_results_for_correct_tenant(self) -> None:
        """Items from the requested tenant are returned."""
        tid = uuid4()
        chunk = uuid4()
        index = [_make_vector(chunk_id=chunk, tenant_id=tid)]
        provider = FakeVectorSearchProvider(index)

        results = asyncio_run(provider.search([0.1, 0.2, 0.3], tenant_id=tid))
        assert len(results) == 1
        assert results[0].chunk_id == chunk

    def test_bounded_by_candidate_top_k(self) -> None:
        """Returned results do not exceed candidate_top_k."""
        tid = uuid4()
        index = [_make_vector(chunk_id=uuid4(), tenant_id=tid) for _ in range(20)]
        provider = FakeVectorSearchProvider(index)

        results = asyncio_run(provider.search([0.1, 0.2, 0.3], tenant_id=tid, candidate_top_k=5))
        assert len(results) <= 5

    @pytest.mark.parametrize("bad_tenant", [None, UUID(int=0)])
    def test_search_raises_on_empty_tenant(self, bad_tenant: UUID | None) -> None:
        """Search raises ValueError when tenant_id is None or zero."""
        provider = FakeVectorSearchProvider()
        with pytest.raises(ValueError, match="tenant_id"):
            asyncio_run(provider.search([0.1, 0.2, 0.3], tenant_id=bad_tenant))  # type: ignore[arg-type]

    def test_visibility_filter_respected(self) -> None:
        """Items with disallowed visibility are excluded."""
        tid = uuid4()
        public_chunk = uuid4()
        private_chunk = uuid4()
        index = [
            _make_vector(chunk_id=public_chunk, tenant_id=tid, visibility="public"),
            _make_vector(chunk_id=private_chunk, tenant_id=tid, visibility="private"),
        ]
        provider = FakeVectorSearchProvider(index)

        results = asyncio_run(
            provider.search([0.1, 0.2, 0.3], tenant_id=tid, visibility=["public"])
        )
        assert {r.chunk_id for r in results} == {public_chunk}

    def test_active_only_filter_respected(self) -> None:
        """Inactive items are excluded when active_only=True."""
        tid = uuid4()
        active_chunk = uuid4()
        inactive_chunk = uuid4()
        index = [
            _make_vector(chunk_id=active_chunk, tenant_id=tid, is_active=True),
            _make_vector(chunk_id=inactive_chunk, tenant_id=tid, is_active=False),
        ]
        provider = FakeVectorSearchProvider(index)

        results = asyncio_run(provider.search([0.1, 0.2, 0.3], tenant_id=tid, active_only=True))
        assert {r.chunk_id for r in results} == {active_chunk}

    def test_active_only_false_includes_inactive(self) -> None:
        """Inactive items are included when active_only=False."""
        tid = uuid4()
        index = [
            _make_vector(chunk_id=uuid4(), tenant_id=tid, is_active=False),
        ]
        provider = FakeVectorSearchProvider(index)

        results = asyncio_run(provider.search([0.1, 0.2, 0.3], tenant_id=tid, active_only=False))
        assert len(results) == 1

    def test_locale_filter_respected(self) -> None:
        """Items with non-matching locale are excluded."""
        tid = uuid4()
        en_chunk = uuid4()
        vi_chunk = uuid4()
        index = [
            _make_vector(chunk_id=en_chunk, tenant_id=tid, locale="en"),
            _make_vector(chunk_id=vi_chunk, tenant_id=tid, locale="vi"),
        ]
        provider = FakeVectorSearchProvider(index)

        results = asyncio_run(
            provider.search([0.1, 0.2, 0.3], tenant_id=tid, locale="en")
        )
        assert {r.chunk_id for r in results} == {en_chunk}

    def test_source_allowlist_filter_respected(self) -> None:
        """Items outside the source allowlist are excluded."""
        tid = uuid4()
        allowed_source = uuid4()
        blocked_source = uuid4()
        allowed_chunk = uuid4()
        blocked_chunk = uuid4()
        index = [
            _make_vector(chunk_id=allowed_chunk, tenant_id=tid, source_id=allowed_source),
            _make_vector(chunk_id=blocked_chunk, tenant_id=tid, source_id=blocked_source),
        ]
        provider = FakeVectorSearchProvider(index)

        results = asyncio_run(
            provider.search(
                [0.1, 0.2, 0.3],
                tenant_id=tid,
                source_allowlist=[allowed_source],
            )
        )
        assert {r.chunk_id for r in results} == {allowed_chunk}

    def test_vector_dimension_mismatch_raises(self) -> None:
        """Mismatched query/index vector dimensions fail loudly."""
        tid = uuid4()
        provider = FakeVectorSearchProvider([_make_vector(tenant_id=tid)])

        with pytest.raises(ValueError, match="vector dimensions"):
            asyncio_run(provider.search([0.1, 0.2], tenant_id=tid))


# ── FakeKeywordSearchProvider ──────────────────────────────────────────


class TestFakeKeywordSearchProvider:
    """In-memory keyword search, filtering, and tenant isolation."""

    def test_conforms_to_protocol(self) -> None:
        """FakeKeywordSearchProvider satisfies the KeywordSearchProvider protocol."""
        provider = FakeKeywordSearchProvider()
        assert isinstance(provider, KeywordSearchProvider)

    def test_returns_empty_when_no_match(self) -> None:
        """Search returns empty when no items contain the query text."""
        tid = uuid4()
        index = [_make_keyword_item(tenant_id=tid, text="hello world")]
        provider = FakeKeywordSearchProvider(index)

        results = asyncio_run(provider.search("goodbye", tenant_id=tid))
        assert results == []

    def test_case_insensitive_matching(self) -> None:
        """Substring match is case-insensitive."""
        tid = uuid4()
        chunk = uuid4()
        index = [_make_keyword_item(chunk_id=chunk, tenant_id=tid, text="Hello World")]
        provider = FakeKeywordSearchProvider(index)

        results = asyncio_run(provider.search("hello", tenant_id=tid))
        assert len(results) == 1
        assert results[0].chunk_id == chunk

    def test_tenant_isolation(self) -> None:
        """Items from other tenants are not returned."""
        tid_a = uuid4()
        tid_b = uuid4()
        index = [_make_keyword_item(tenant_id=tid_a, text="hello")]
        provider = FakeKeywordSearchProvider(index)

        results = asyncio_run(provider.search("hello", tenant_id=tid_b))
        assert results == []

    @pytest.mark.parametrize("bad_tenant", [None, UUID(int=0)])
    def test_search_raises_on_empty_tenant(self, bad_tenant: UUID | None) -> None:
        """Search raises ValueError when tenant_id is None or zero."""
        provider = FakeKeywordSearchProvider()
        with pytest.raises(ValueError, match="tenant_id"):
            asyncio_run(provider.search("hello", tenant_id=bad_tenant))  # type: ignore[arg-type]

    def test_results_bounded_by_top_k(self) -> None:
        """Keyword search respects candidate_top_k."""
        tid = uuid4()
        index = [
            _make_keyword_item(chunk_id=uuid4(), tenant_id=tid, text="hello world")
            for _ in range(10)
        ]
        provider = FakeKeywordSearchProvider(index)

        results = asyncio_run(provider.search("hello", tenant_id=tid, candidate_top_k=3))
        assert len(results) <= 3

    def test_source_allowlist_filter_respected(self) -> None:
        """Items outside the source allowlist are excluded."""
        tid = uuid4()
        allowed_source = uuid4()
        blocked_source = uuid4()
        allowed_chunk = uuid4()
        blocked_chunk = uuid4()
        index = [
            _make_keyword_item(chunk_id=allowed_chunk, tenant_id=tid, source_id=allowed_source, text="hello"),
            _make_keyword_item(chunk_id=blocked_chunk, tenant_id=tid, source_id=blocked_source, text="hello"),
        ]
        provider = FakeKeywordSearchProvider(index)

        results = asyncio_run(
            provider.search("hello", tenant_id=tid, source_allowlist=[allowed_source])
        )
        assert {r.chunk_id for r in results} == {allowed_chunk}


# ── FakeHybridRetriever ────────────────────────────────────────────────


class TestFakeHybridRetriever:
    """RRF fusion, deduplication, tenant isolation."""

    def test_returns_fused_candidates(self) -> None:
        """Hybrid search returns candidates from both vector and keyword branches."""
        tid = uuid4()
        chunk = uuid4()

        vec_index = [_make_vector(chunk_id=chunk, tenant_id=tid, text="alpha beta")]
        kw_index = [_make_keyword_item(chunk_id=chunk, tenant_id=tid, text="alpha beta")]

        hybrid = FakeHybridRetriever(
            FakeVectorSearchProvider(vec_index),
            FakeKeywordSearchProvider(kw_index),
        )

        results = asyncio_run(
            hybrid.search(
                query_text="alpha",
                query_embedding=[0.1, 0.2, 0.3],
                tenant_id=tid,
            )
        )
        assert len(results) >= 1
        assert any(r.chunk_id == chunk for r in results)

    def test_deduplicates_by_chunk_id(self) -> None:
        """Same chunk_id appearing in both branches appears only once."""
        tid = uuid4()
        chunk = uuid4()

        vec_index = [_make_vector(chunk_id=chunk, tenant_id=tid, text="alpha beta")]
        kw_index = [_make_keyword_item(chunk_id=chunk, tenant_id=tid, text="alpha beta")]

        hybrid = FakeHybridRetriever(
            FakeVectorSearchProvider(vec_index),
            FakeKeywordSearchProvider(kw_index),
        )

        results = asyncio_run(
            hybrid.search(
                query_text="alpha",
                query_embedding=[0.1, 0.2, 0.3],
                tenant_id=tid,
            )
        )
        chunk_ids = [r.chunk_id for r in results]
        assert len(chunk_ids) == len(set(chunk_ids)), "chunk_id duplicates found"

    def test_rrf_boosts_items_in_both_branches(self) -> None:
        """Items appearing in both branches get a higher fused score."""
        tid = uuid4()
        both_chunk = uuid4()
        vec_only_chunk = uuid4()

        vec_index = [
            _make_vector(chunk_id=both_chunk, tenant_id=tid, text="alpha beta"),
            _make_vector(chunk_id=vec_only_chunk, tenant_id=tid, text="gamma delta"),
        ]
        kw_index = [
            _make_keyword_item(chunk_id=both_chunk, tenant_id=tid, text="alpha beta"),
        ]

        hybrid = FakeHybridRetriever(
            FakeVectorSearchProvider(vec_index),
            FakeKeywordSearchProvider(kw_index),
        )

        results = asyncio_run(
            hybrid.search(
                query_text="alpha",
                query_embedding=[0.1, 0.2, 0.3],
                tenant_id=tid,
            )
        )

        both_scores = {r.chunk_id: r.score for r in results}
        assert both_scores.get(both_chunk, 0) > both_scores.get(vec_only_chunk, 0)

    def test_source_allowlist_filter_respected(self) -> None:
        """Hybrid retrieval applies the source allowlist to both branches."""
        tid = uuid4()
        allowed_source = uuid4()
        blocked_source = uuid4()
        allowed_chunk = uuid4()
        blocked_chunk = uuid4()
        vec_index = [
            _make_vector(chunk_id=allowed_chunk, tenant_id=tid, source_id=allowed_source),
            _make_vector(chunk_id=blocked_chunk, tenant_id=tid, source_id=blocked_source),
        ]
        kw_index = [
            _make_keyword_item(chunk_id=allowed_chunk, tenant_id=tid, source_id=allowed_source, text="alpha"),
            _make_keyword_item(chunk_id=blocked_chunk, tenant_id=tid, source_id=blocked_source, text="alpha"),
        ]
        hybrid = FakeHybridRetriever(
            FakeVectorSearchProvider(vec_index),
            FakeKeywordSearchProvider(kw_index),
        )

        results = asyncio_run(
            hybrid.search(
                query_text="alpha",
                query_embedding=[0.1, 0.2, 0.3],
                tenant_id=tid,
                source_allowlist=[allowed_source],
            )
        )
        assert {r.chunk_id for r in results} == {allowed_chunk}

    def test_final_top_k_bounded(self) -> None:
        """Results are bounded by final_top_k."""
        tid = uuid4()
        chunks = [uuid4() for _ in range(20)]
        vec_index = [_make_vector(chunk_id=c, tenant_id=tid) for c in chunks]
        kw_index = [_make_keyword_item(chunk_id=c, tenant_id=tid) for c in chunks]

        hybrid = FakeHybridRetriever(
            FakeVectorSearchProvider(vec_index),
            FakeKeywordSearchProvider(kw_index),
        )

        results = asyncio_run(
            hybrid.search(
                query_text="hello",
                query_embedding=[0.1, 0.2, 0.3],
                tenant_id=tid,
                final_top_k=5,
            )
        )
        assert len(results) <= 5

    def test_conforms_to_protocol(self) -> None:
        """FakeHybridRetriever satisfies the HybridRetriever protocol."""
        hybrid = FakeHybridRetriever(
            FakeVectorSearchProvider(),
            FakeKeywordSearchProvider(),
        )
        assert isinstance(hybrid, HybridRetriever)

    @pytest.mark.parametrize("bad_tenant", [None, UUID(int=0)])
    def test_search_raises_on_empty_tenant(self, bad_tenant: UUID | None) -> None:
        """Search raises ValueError when tenant_id is None or zero."""
        hybrid = FakeHybridRetriever(
            FakeVectorSearchProvider(),
            FakeKeywordSearchProvider(),
        )
        with pytest.raises(ValueError, match="tenant_id"):
            asyncio_run(
                hybrid.search(
                    query_text="hello",
                    query_embedding=[0.1, 0.2],
                    tenant_id=bad_tenant,  # type: ignore[arg-type]
                )
            )


# ── FakeReranker ───────────────────────────────────────────────────────


class TestFakeReranker:
    """Score threshold filtering and rank assignment."""

    def test_returns_filtered_results(self) -> None:
        """Results below min_score are dropped."""
        reranker = FakeReranker(min_score=0.5)
        candidates = [
            VectorResult(chunk_id=uuid4(), score=0.9),
            VectorResult(chunk_id=uuid4(), score=0.3),
            VectorResult(chunk_id=uuid4(), score=0.7),
        ]

        results = asyncio_run(reranker.rerank("query", candidates, top_k=10))
        assert len(results) == 2
        assert all(r.score >= 0.5 for r in results)

    def test_assigns_rank_positions(self) -> None:
        """Reranked results have correct rank positions."""
        reranker = FakeReranker(min_score=0.0)
        candidates = [
            VectorResult(chunk_id=uuid4(), score=0.3),
            VectorResult(chunk_id=uuid4(), score=0.9),
            VectorResult(chunk_id=uuid4(), score=0.6),
        ]

        results = asyncio_run(reranker.rerank("query", candidates, top_k=10))
        assert len(results) == 3
        # Highest score first
        assert results[0].rank == 0
        assert results[0].score == 0.9
        assert results[1].rank == 1
        assert results[1].score == 0.6
        assert results[2].rank == 2
        assert results[2].score == 0.3

    def test_respects_top_k(self) -> None:
        """Top-k bound is honored after filtering."""
        reranker = FakeReranker(min_score=0.0)
        candidates = [VectorResult(chunk_id=uuid4(), score=0.5) for _ in range(10)]

        results = asyncio_run(reranker.rerank("query", candidates, top_k=3))
        assert len(results) == 3


# ── Tenant fail-closed (all three provider types) ──────────────────────


class TestTenantFailClosed:
    """Every provider type MUST reject missing/empty tenant_id."""

    @pytest.mark.parametrize(
        "provider_name",
        ["vector", "keyword", "hybrid"],
    )
    def test_none_tenant_raises(self, provider_name: str) -> None:
        """All three provider types raise on None tenant_id."""
        if provider_name == "vector":
            provider = FakeVectorSearchProvider()
            coro = provider.search([0.1], tenant_id=None)  # type: ignore[arg-type]
        elif provider_name == "keyword":
            provider = FakeKeywordSearchProvider()
            coro = provider.search("hello", tenant_id=None)  # type: ignore[arg-type]
        else:
            hybrid = FakeHybridRetriever(
                FakeVectorSearchProvider(), FakeKeywordSearchProvider()
            )
            coro = hybrid.search("hello", [0.1], tenant_id=None)  # type: ignore[arg-type]

        with pytest.raises(ValueError, match="tenant_id"):
            asyncio_run(coro)

    @pytest.mark.parametrize(
        "provider_name",
        ["vector", "keyword", "hybrid"],
    )
    def test_zero_tenant_raises(self, provider_name: str) -> None:
        """All three provider types raise on zero/UUID(int=0) tenant_id."""
        zero = UUID(int=0)
        if provider_name == "vector":
            provider = FakeVectorSearchProvider()
            coro = provider.search([0.1], tenant_id=zero)
        elif provider_name == "keyword":
            provider = FakeKeywordSearchProvider()
            coro = provider.search("hello", tenant_id=zero)
        else:
            hybrid = FakeHybridRetriever(
                FakeVectorSearchProvider(), FakeKeywordSearchProvider()
            )
            coro = hybrid.search("hello", [0.1], tenant_id=zero)

        with pytest.raises(ValueError, match="tenant_id"):
            asyncio_run(coro)


# ── RetrievalQuery model ────────────────────────────────────────────────


class TestRetrievalQuery:
    """Pydantic model shape and defaults."""

    def test_defaults(self) -> None:
        """RetrievalQuery has sensible defaults after tenant is supplied."""
        q = RetrievalQuery(tenant_id=uuid4())
        assert q.retrieval_mode == RetrievalMode.hybrid
        assert q.candidate_top_k == 50
        assert q.final_top_k == 10
        assert q.min_score == 0.0
        assert q.visibility == ["public"]
        assert q.active_only is True

    def test_retrieval_mode_enum_values(self) -> None:
        """All enum values are accessible."""
        assert RetrievalMode.hybrid.value == "hybrid"
        assert RetrievalMode.vector.value == "vector"
        assert RetrievalMode.keyword.value == "keyword"

    def test_frozen(self) -> None:
        """RetrievalQuery instances are frozen (immutable)."""
        q = RetrievalQuery(tenant_id=uuid4())
        with pytest.raises((ValueError, RuntimeError)):
            q.tenant_id = uuid4()  # type: ignore[misc]

    def test_requires_tenant_id(self) -> None:
        """RetrievalQuery fails validation without tenant_id."""
        with pytest.raises(ValueError):
            RetrievalQuery()

    def test_candidate_top_k_bounds(self) -> None:
        """candidate_top_k is clamped to [1, 500]."""
        tid = uuid4()
        RetrievalQuery(tenant_id=tid, candidate_top_k=1)
        RetrievalQuery(tenant_id=tid, candidate_top_k=500)
        with pytest.raises(ValueError):
            RetrievalQuery(tenant_id=tid, candidate_top_k=0)
        with pytest.raises(ValueError):
            RetrievalQuery(tenant_id=tid, candidate_top_k=501)


# ── Async helper ─────────────────────────────────────────────────────


def asyncio_run(coro):
    """Run a coroutine synchronously for test convenience."""
    import asyncio

    return asyncio.run(coro)
