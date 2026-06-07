"""Tenant-scoped rag.search capability backed by hybrid retrieval."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.vector.contracts import HybridRetriever, Reranker
from app.vector.fake import FakeEmbeddingProvider, FakeReranker
from app.vector.models import RetrievalMode


class RagSearchCapability:
    """Execute bounded hybrid retrieval without exposing backend-specific clients."""

    def __init__(
        self,
        retriever: HybridRetriever,
        embedding_provider: FakeEmbeddingProvider | None = None,
        reranker: Reranker | None = None,
    ) -> None:
        """Initialize with retrieval dependencies."""
        self._retriever = retriever
        self._embedding_provider = embedding_provider or FakeEmbeddingProvider(dimension=16)
        self._reranker = reranker or FakeReranker()

    async def __call__(self, args: dict[str, Any], *, tenant_id: UUID | None = None) -> dict[str, Any]:
        """Run retrieval and return structured snippets, citations, or refusal."""
        if tenant_id is None or tenant_id == UUID(int=0):
            return {"status": "refused", "refusal_reason": "missing_tenant", "snippets": [], "citations": []}
        query = str(args.get("query", "")).strip()
        if not query:
            return {"status": "refused", "refusal_reason": "empty_query", "snippets": [], "citations": []}
        final_top_k = min(int(args.get("final_top_k", 5)), 10)
        candidate_top_k = min(int(args.get("candidate_top_k", 50)), 100)
        min_score = float(args.get("min_score", 0.0))
        visibility = args.get("visibility") or ["public"]
        source_allowlist = [UUID(str(v)) for v in args.get("source_allowlist", [])]
        source_version_ids = [UUID(str(v)) for v in args.get("source_version_ids", [])]
        mode = RetrievalMode(args.get("retrieval_mode", "hybrid"))
        embedding = await self._embedding_provider.embed_query(query, tenant_id)
        candidates = await self._retriever.search(
            query_text=query,
            query_embedding=embedding,
            tenant_id=tenant_id,
            candidate_top_k=candidate_top_k,
            final_top_k=final_top_k,
            visibility=visibility,
            source_allowlist=source_allowlist or None,
            locale=args.get("locale"),
            active_only=True,
            source_version_ids=source_version_ids or None,
        )
        ranked = await self._reranker.rerank(query, candidates, top_k=final_top_k)
        ranked = [hit for hit in ranked if hit.score >= min_score]
        if not ranked:
            return {"status": "refused", "refusal_reason": "no_relevant_knowledge", "snippets": [], "citations": []}
        snippets = []
        citations = []
        for hit in ranked:
            payload = hit.payload
            snippets.append(
                {
                    "chunk_id": str(hit.chunk_id),
                    "text": str(payload.get("text", ""))[:1200],
                    "score": hit.score,
                    "section_path": payload.get("section_path", []),
                }
            )
            citations.append(
                {
                    "chunk_id": str(hit.chunk_id),
                    "source_id": str(payload.get("source_id", "")),
                    "source_version_id": str(payload.get("source_version_id", "")),
                    "source_title": payload.get("source_title"),
                    "source_uri": payload.get("source_uri"),
                    "section_path": payload.get("section_path", []),
                    "score": hit.score,
                }
            )
        return {
            "status": "ok",
            "retrieval_mode": mode.value,
            "snippets": snippets,
            "citations": citations,
            "audit": {
                "tenant_id": str(tenant_id),
                "candidate_count": len(candidates),
                "returned_count": len(snippets),
            },
        }
