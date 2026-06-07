# ruff: noqa
from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.knowledge.keyword_search import InMemoryBM25KeywordSearchProvider, KeywordDocument
from app.knowledge.retrieval import ReciprocalRankFusionHybridRetriever
from app.vector.contracts import VectorResult


class StaticVectorProvider:
    def __init__(self, results: list[VectorResult]) -> None:
        self.results = results
        self.calls = []

    async def search(self, **kwargs):
        self.calls.append(kwargs)
        tenant_id = kwargs["tenant_id"]
        if tenant_id is None or tenant_id == UUID(int=0):
            raise ValueError("tenant_id must not be None or zero")
        return self.results[: kwargs.get("candidate_top_k", 50)]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_bm25_provider_filters_by_tenant_visibility_active_source_and_locale() -> None:
    tenant_id = uuid4()
    other_tenant = uuid4()
    source_id = uuid4()
    version_id = uuid4()
    matching = uuid4()
    provider = InMemoryBM25KeywordSearchProvider(
        [
            KeywordDocument(
                matching, tenant_id, "Exact SKU-123 refund policy", "private", "en", True, version_id, source_id
            ),
            KeywordDocument(uuid4(), other_tenant, "Exact SKU-123 leak", "private", "en", True, version_id, source_id),
            KeywordDocument(
                uuid4(), tenant_id, "Exact SKU-123 inactive", "private", "en", False, version_id, source_id
            ),
        ]
    )

    results = await provider.search(
        "SKU-123",
        tenant_id,
        visibility=["private"],
        source_allowlist=[source_id],
        source_version_ids=[version_id],
        locale="en",
    )

    assert [result.chunk_id for result in results] == [matching]


@pytest.mark.anyio
async def test_bm25_provider_fails_closed_without_tenant() -> None:
    provider = InMemoryBM25KeywordSearchProvider([])

    with pytest.raises(ValueError):
        await provider.search("anything", UUID(int=0))


@pytest.mark.anyio
async def test_hybrid_retriever_deduplicates_and_fuses_rrf_scores() -> None:
    tenant_id = uuid4()
    duplicate = uuid4()
    vector_only = uuid4()
    keyword_provider = InMemoryBM25KeywordSearchProvider(
        [
            KeywordDocument(duplicate, tenant_id, "SKU-999 exact fact", payload={"branch": "keyword"}),
        ]
    )
    vector_provider = StaticVectorProvider(
        [
            VectorResult(vector_only, 0.99, {"branch": "vector"}),
            VectorResult(duplicate, 0.88, {"branch": "vector"}),
        ]
    )
    retriever = ReciprocalRankFusionHybridRetriever(vector_provider, keyword_provider)

    results = await retriever.search("SKU-999", [0.1], tenant_id, final_top_k=5)

    assert [result.chunk_id for result in results] == [duplicate, vector_only]
    assert results[0].payload["vector_score"] == 0.88
    assert results[0].payload["keyword_score"] > 0


@pytest.mark.anyio
async def test_hybrid_retriever_bounds_final_top_k_to_ten() -> None:
    tenant_id = uuid4()
    vector_provider = StaticVectorProvider([VectorResult(uuid4(), 1.0, {}) for _ in range(20)])
    keyword_provider = InMemoryBM25KeywordSearchProvider([])
    retriever = ReciprocalRankFusionHybridRetriever(vector_provider, keyword_provider)

    results = await retriever.search("query", [0.1], tenant_id, final_top_k=99)

    assert len(results) == 10


@pytest.mark.anyio
async def test_hybrid_retriever_propagates_filters_to_branches() -> None:
    tenant_id = uuid4()
    source_id = uuid4()
    vector_provider = StaticVectorProvider([])
    keyword_provider = InMemoryBM25KeywordSearchProvider([])
    retriever = ReciprocalRankFusionHybridRetriever(vector_provider, keyword_provider)

    await retriever.search("query", [0.1], tenant_id, visibility=["private"], source_allowlist=[source_id])

    assert vector_provider.calls[0]["visibility"] == ["private"]
    assert vector_provider.calls[0]["source_allowlist"] == [source_id]
