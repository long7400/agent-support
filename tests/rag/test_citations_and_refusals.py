# pyright: reportArgumentType=false, reportIndexIssue=false
# ruff: noqa: D101,D102,D103,D107
"""Tests for RAG citation metadata and refusal states."""

from uuid import uuid4

import pytest


from app.agent_harness.capabilities.rag_search import RagSearchCapability
from app.vector.contracts import VectorResult


@pytest.fixture
def anyio_backend():
    return "asyncio"


class StubRetriever:
    def __init__(self, results):
        self.results = results
        self.calls = []

    async def search(self, **kwargs):
        self.calls.append(kwargs)
        return self.results


@pytest.mark.anyio
async def test_rag_search_returns_bounded_citations():
    tenant_id = uuid4()
    source_id = uuid4()
    version_id = uuid4()
    chunk_id = uuid4()
    result = VectorResult(
        chunk_id=chunk_id,
        score=0.9,
        payload={
            "text": "answer text",
            "source_id": source_id,
            "source_version_id": version_id,
            "source_title": "Runbook",
            "source_uri": "kb://runbook",
            "section_path": ["Billing"],
        },
    )
    capability = RagSearchCapability(StubRetriever([result]))

    response = await capability({"query": "billing", "final_top_k": 99}, tenant_id=tenant_id)

    assert response["status"] == "ok"
    assert len(response["snippets"]) == 1
    assert response["snippets"][0]["citation"] == {
        "source_id": str(source_id),
        "source_version_id": str(version_id),
        "chunk_id": str(chunk_id),
    }
    assert response["citations"][0]["source_uri"] == "kb://runbook"
    assert response["audit"]["returned_count"] == 1


@pytest.mark.anyio
async def test_rag_search_refuses_missing_empty_denied_and_low_confidence():
    low_result = VectorResult(chunk_id=uuid4(), score=0.2, payload={"text": "weak evidence"})
    capability = RagSearchCapability(StubRetriever([low_result]))

    missing = await capability({"query": "x"}, tenant_id=None)
    empty = await capability({"query": "   "}, tenant_id=uuid4())
    denied = await capability({"query": "x", "retrieval_denied": True}, tenant_id=uuid4())
    low = await capability({"query": "x", "min_score": 1.0}, tenant_id=uuid4())

    assert missing["refusal_reason"] == "missing_tenant"
    assert empty["refusal_reason"] == "empty_query"
    assert denied["refusal_reason"] == "retrieval_denied"
    assert low["refusal_reason"] == "below_threshold"


@pytest.mark.anyio
async def test_rag_search_refuses_no_results_before_reranking():
    capability = RagSearchCapability(StubRetriever([]))

    response = await capability({"query": "unknown"}, tenant_id=uuid4())

    assert response == {"status": "refused", "refusal_reason": "no_results", "snippets": [], "citations": []}


@pytest.mark.anyio
async def test_rag_search_refuses_malformed_numeric_args():
    capability = RagSearchCapability(StubRetriever([]))

    for args in (
        {"query": "x", "final_top_k": "abc"},
        {"query": "x", "candidate_top_k": None},
        {"query": "x", "min_score": "not-a-float"},
    ):
        response = await capability(args, tenant_id=uuid4())

        assert response["status"] == "refused"
        assert response["refusal_reason"] == "invalid_numeric_arg"
        assert response["snippets"] == []


@pytest.mark.anyio
async def test_rag_search_lower_bounds_candidate_top_k():
    retriever = StubRetriever([])
    capability = RagSearchCapability(retriever)

    response = await capability({"query": "x", "candidate_top_k": -1}, tenant_id=uuid4())

    assert response["refusal_reason"] == "no_results"
    assert retriever.calls[0]["candidate_top_k"] == 1


@pytest.mark.anyio
async def test_rag_search_clarifies_when_retrieval_is_stale():
    result = VectorResult(chunk_id=uuid4(), score=0.9, payload={"text": "old", "is_stale": True})
    capability = RagSearchCapability(StubRetriever([result]))

    response = await capability({"query": "policy"}, tenant_id=uuid4())

    assert response["status"] == "clarification_required"
    assert response["refusal_reason"] == "stale_knowledge"
    assert response["snippets"] == []


@pytest.mark.anyio
async def test_rag_search_bounds_final_snippets_and_output_size():
    results = [VectorResult(chunk_id=uuid4(), score=1.0 - (i / 100), payload={"text": "x" * 1200}) for i in range(20)]
    capability = RagSearchCapability(StubRetriever(results))

    response = await capability({"query": "x", "final_top_k": 20}, tenant_id=uuid4())

    assert response["status"] == "ok"
    assert len(response["snippets"]) <= 10
    assert sum(len(s["text"]) for s in response["snippets"]) <= 4000
