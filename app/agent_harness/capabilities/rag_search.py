"""Tenant-scoped rag.search capability backed by hybrid retrieval."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.infra.observability import record_rag_observability_event
from app.vector.contracts import HybridRetriever, Reranker
from app.vector.fake import FakeEmbeddingProvider, FakeReranker
from app.vector.models import RetrievalMode

MAX_SNIPPET_CHARS = 1200
MAX_TOTAL_SNIPPET_CHARS = 4000
MAX_FINAL_TOP_K = 10

NUMERIC_ARG_REFUSAL = {"status": "refused", "refusal_reason": "invalid_numeric_arg", "snippets": [], "citations": []}


def _bounded_int(value: Any, *, lower: int, upper: int) -> int | None:
    try:
        return max(lower, min(int(value), upper))
    except (TypeError, ValueError):
        return None


def _float_arg(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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
            record_rag_observability_event("rag.search.refused", refusal_reason="missing_tenant", status="refused")
            return {"status": "refused", "refusal_reason": "missing_tenant", "snippets": [], "citations": []}
        query = str(args.get("query", "")).strip()
        if not query:
            record_rag_observability_event("rag.search.refused", tenant_id=str(tenant_id), refusal_reason="empty_query", status="refused")
            return {"status": "refused", "refusal_reason": "empty_query", "snippets": [], "citations": []}
        if args.get("retrieval_denied") is True:
            record_rag_observability_event("rag.search.refused", tenant_id=str(tenant_id), refusal_reason="retrieval_denied", status="refused")
            return {"status": "refused", "refusal_reason": "retrieval_denied", "snippets": [], "citations": []}
        final_top_k = _bounded_int(args.get("final_top_k", 5), lower=1, upper=MAX_FINAL_TOP_K)
        candidate_top_k = _bounded_int(args.get("candidate_top_k", 50), lower=1, upper=100)
        min_score = _float_arg(args.get("min_score", 0.0))
        if final_top_k is None or candidate_top_k is None or min_score is None:
            record_rag_observability_event("rag.search.refused", tenant_id=str(tenant_id), refusal_reason="invalid_numeric_arg", status="refused")
            return NUMERIC_ARG_REFUSAL.copy()
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
        if not candidates:
            record_rag_observability_event(
                "rag.search.refused",
                tenant_id=str(tenant_id),
                retrieval_mode=mode.value,
                refusal_reason="no_results",
                status="refused",
            )
            return {"status": "refused", "refusal_reason": "no_results", "snippets": [], "citations": []}
        ranked = await self._reranker.rerank(query, candidates, top_k=final_top_k)
        ranked = [hit for hit in ranked if hit.score >= min_score]
        if not ranked:
            record_rag_observability_event(
                "rag.search.refused",
                tenant_id=str(tenant_id),
                retrieval_mode=mode.value,
                refusal_reason="below_threshold",
                status="refused",
            )
            return {"status": "refused", "refusal_reason": "below_threshold", "snippets": [], "citations": []}
        if any(hit.payload.get("is_stale") is True or hit.payload.get("status") == "stale" for hit in ranked):
            record_rag_observability_event(
                "rag.search.refused",
                tenant_id=str(tenant_id),
                retrieval_mode=mode.value,
                refusal_reason="stale_knowledge",
                status="clarification_required",
            )
            return {
                "status": "clarification_required",
                "refusal_reason": "stale_knowledge",
                "snippets": [],
                "citations": [],
            }
        snippets = []
        citations = []
        total_chars = 0
        for hit in ranked:
            payload = hit.payload
            text = str(payload.get("text", ""))[:MAX_SNIPPET_CHARS]
            remaining = MAX_TOTAL_SNIPPET_CHARS - total_chars
            if remaining <= 0:
                break
            text = text[:remaining]
            total_chars += len(text)
            snippets.append(
                {
                    "chunk_id": str(hit.chunk_id),
                    "text": text,
                    "score": hit.score,
                    "section_path": payload.get("section_path", []),
                    "citation": {
                        "source_id": str(payload.get("source_id", "")),
                        "source_version_id": str(payload.get("source_version_id", "")),
                        "chunk_id": str(hit.chunk_id),
                    },
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
        if not snippets:
            record_rag_observability_event(
                "rag.search.refused",
                tenant_id=str(tenant_id),
                retrieval_mode=mode.value,
                refusal_reason="output_limit_exceeded",
                status="refused",
            )
            return {"status": "refused", "refusal_reason": "output_limit_exceeded", "snippets": [], "citations": []}
        cited_version_ids = sorted({citation["source_version_id"] for citation in citations})
        cited_source_ids = sorted({citation["source_id"] for citation in citations})
        record_rag_observability_event(
            "rag.search.completed",
            tenant_id=str(tenant_id),
            retrieval_mode=mode.value,
            source_ids=cited_source_ids,
            source_version_ids=cited_version_ids,
            candidate_count=len(candidates),
            returned_count=len(snippets),
            final_top_k=final_top_k,
            candidate_top_k=candidate_top_k,
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
