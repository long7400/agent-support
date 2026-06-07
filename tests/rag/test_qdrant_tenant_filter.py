# ruff: noqa
from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.vector.qdrant import QdrantVectorSearchProvider, build_qdrant_filter


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def test_build_qdrant_filter_requires_tenant() -> None:
    with pytest.raises(ValueError):
        build_qdrant_filter(tenant_id=UUID(int=0))


def test_build_qdrant_filter_includes_mandatory_filters() -> None:
    tenant_id = uuid4()
    source_id = uuid4()
    version_id = uuid4()

    query_filter = build_qdrant_filter(
        tenant_id=tenant_id,
        visibility=["public", "private"],
        source_allowlist=[source_id],
        source_version_ids=[version_id],
        locale="en",
    )

    assert {item["key"] for item in query_filter["must"]} == {
        "tenant_id",
        "is_active",
        "visibility",
        "source_id",
        "source_version_id",
        "locale",
    }
    assert query_filter["must"][0] == {"key": "tenant_id", "match": {"value": str(tenant_id)}}


@pytest.mark.anyio
async def test_qdrant_provider_sends_filter_and_maps_hits() -> None:
    tenant_id = uuid4()
    chunk_id = uuid4()
    calls = []

    class Client:
        def search(self, **kwargs):
            calls.append(kwargs)
            return [SimpleNamespace(score=0.7, payload={"chunk_id": str(chunk_id), "tenant_id": str(tenant_id)})]

    provider = QdrantVectorSearchProvider(Client(), "chunks")

    results = await provider.search([0.1, 0.2], tenant_id, visibility=["public"])

    assert results[0].chunk_id == chunk_id
    assert calls[0]["collection_name"] == "chunks"
    assert calls[0]["query_filter"]["must"][0]["key"] == "tenant_id"


@pytest.mark.anyio
async def test_qdrant_provider_fails_before_client_call_without_tenant() -> None:
    class Client:
        def search(self, **kwargs):
            raise AssertionError("client should not be called")

    provider = QdrantVectorSearchProvider(Client(), "chunks")

    with pytest.raises(ValueError):
        await provider.search([0.1], UUID(int=0))
