"""Deterministic in-memory BM25 keyword search provider."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.vector.contracts import KeywordResult

_TOKEN_RE = re.compile(r"[\w.-]+")


@dataclass(frozen=True)
class KeywordDocument:
    """A lexical document available for keyword retrieval."""

    chunk_id: UUID
    tenant_id: UUID
    text: str
    visibility: str = "public"
    locale: str | None = None
    is_active: bool = True
    source_version_id: UUID | None = None
    source_id: UUID | None = None
    payload: dict[str, Any] | None = None


def tokenize(text: str) -> list[str]:
    """Tokenize support-doc text for BM25 scoring."""
    return [token.lower() for token in _TOKEN_RE.findall(text)]


class InMemoryBM25KeywordSearchProvider:
    """Small deterministic BM25 provider for V1 tests and local retrieval."""

    def __init__(self, documents: list[KeywordDocument] | None = None) -> None:
        """Initialize with lexical documents."""
        self._documents = list(documents or [])

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
        """Search filtered documents with BM25 scoring."""
        if tenant_id is None or tenant_id == UUID(int=0):
            raise ValueError("tenant_id must not be None or zero")
        query_terms = tokenize(query_text)
        if not query_terms:
            return []
        allowed_vis = set(visibility or ["public"])
        allowed_src = set(source_allowlist) if source_allowlist else None
        allowed_sv = set(source_version_ids) if source_version_ids else None
        filtered = [
            doc for doc in self._documents
            if doc.tenant_id == tenant_id
            and (not active_only or doc.is_active)
            and doc.visibility in allowed_vis
            and (locale is None or doc.locale == locale)
            and (allowed_src is None or doc.source_id in allowed_src)
            and (allowed_sv is None or doc.source_version_id in allowed_sv)
        ]
        if not filtered:
            return []
        tokenized = [tokenize(doc.text) for doc in filtered]
        avg_len = sum(len(tokens) for tokens in tokenized) / max(len(tokenized), 1)
        results: list[KeywordResult] = []
        for doc, tokens in zip(filtered, tokenized, strict=True):
            score = _bm25_score(query_terms, tokens, tokenized, avg_len)
            if score > 0:
                results.append(KeywordResult(doc.chunk_id, score, dict(doc.payload or {})))
        results.sort(key=lambda item: item.score, reverse=True)
        return results[:candidate_top_k]


def _bm25_score(query_terms: list[str], doc_tokens: list[str], corpus: list[list[str]], avg_len: float) -> float:
    k1 = 1.5
    b = 0.75
    doc_len = len(doc_tokens) or 1
    score = 0.0
    for term in query_terms:
        freq = doc_tokens.count(term)
        if freq == 0:
            continue
        containing = sum(1 for tokens in corpus if term in tokens)
        idf = math.log(1 + (len(corpus) - containing + 0.5) / (containing + 0.5))
        denom = freq + k1 * (1 - b + b * doc_len / max(avg_len, 1.0))
        score += idf * (freq * (k1 + 1)) / denom
    return score
