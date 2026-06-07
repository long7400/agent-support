"""Qdrant implementation of the dense vector provider contract."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.vector.contracts import VectorResult


class QdrantVectorSearchProvider:
    """Dense search provider that always applies tenant payload filters."""

    def __init__(self, client: Any, collection_name: str) -> None:
        """Initialize with a Qdrant-compatible client."""
        self._client = client
        self._collection_name = collection_name

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
        """Search Qdrant after building mandatory tenant filters."""
        if tenant_id is None or tenant_id == UUID(int=0):
            raise ValueError("tenant_id must not be None or zero")
        query_filter = build_qdrant_filter(
            tenant_id=tenant_id,
            visibility=visibility,
            source_allowlist=source_allowlist,
            locale=locale,
            active_only=active_only,
            source_version_ids=source_version_ids,
        )
        search = getattr(self._client, "search", None)
        if search is None:
            raise TypeError("qdrant client must expose search")
        response = search(
            collection_name=self._collection_name,
            query_vector=query_embedding,
            limit=candidate_top_k,
            query_filter=query_filter,
            with_payload=True,
        )
        if hasattr(response, "__await__"):
            response = await response
        return [
            VectorResult(
                chunk_id=UUID(str(hit.payload["chunk_id"])),
                score=float(hit.score),
                payload=dict(hit.payload),
            )
            for hit in response
        ]


def build_qdrant_filter(
    *,
    tenant_id: UUID,
    visibility: list[str] | None = None,
    source_allowlist: list[UUID] | None = None,
    locale: str | None = None,
    active_only: bool = True,
    source_version_ids: list[UUID] | None = None,
) -> dict[str, Any]:
    """Build a Qdrant-compatible payload filter with mandatory tenant match."""
    if tenant_id is None or tenant_id == UUID(int=0):
        raise ValueError("tenant_id must not be None or zero")
    must: list[dict[str, Any]] = [{"key": "tenant_id", "match": {"value": str(tenant_id)}}]
    if active_only:
        must.append({"key": "is_active", "match": {"value": True}})
    if visibility:
        must.append({"key": "visibility", "match": {"any": visibility}})
    if source_allowlist:
        must.append({"key": "source_id", "match": {"any": [str(value) for value in source_allowlist]}})
    if source_version_ids:
        must.append({"key": "source_version_id", "match": {"any": [str(value) for value in source_version_ids]}})
    if locale is not None:
        must.append({"key": "locale", "match": {"value": locale}})
    return {"must": must}
