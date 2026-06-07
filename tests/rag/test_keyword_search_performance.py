# ruff: noqa
from __future__ import annotations

from uuid import uuid4

import pytest

from app.knowledge.keyword_search import InMemoryBM25KeywordSearchProvider, KeywordDocument, tokenize


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_bm25_tokenizes_documents_once_at_index_build(monkeypatch) -> None:
    tenant_id = uuid4()
    calls = 0

    def counted_tokenize(text: str) -> list[str]:
        nonlocal calls
        calls += 1
        return tokenize(text)

    import app.knowledge.keyword_search as keyword_search

    monkeypatch.setattr(keyword_search, "tokenize", counted_tokenize)
    provider = InMemoryBM25KeywordSearchProvider([
        KeywordDocument(uuid4(), tenant_id, "alpha beta"),
        KeywordDocument(uuid4(), tenant_id, "alpha gamma"),
    ])

    assert calls == 2
    await provider.search("alpha", tenant_id)
    await provider.search("beta", tenant_id)

    assert calls == 4


@pytest.mark.anyio
async def test_bm25_uses_postings_to_skip_non_matching_documents() -> None:
    tenant_id = uuid4()
    matching = uuid4()
    docs = [KeywordDocument(matching, tenant_id, "rare-token target")]
    docs.extend(KeywordDocument(uuid4(), tenant_id, "common filler") for _ in range(100))
    provider = InMemoryBM25KeywordSearchProvider(docs)

    results = await provider.search("rare-token", tenant_id)

    assert [result.chunk_id for result in results] == [matching]
