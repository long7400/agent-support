"""Deterministic in-memory BM25 keyword search provider."""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
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


@dataclass(frozen=True)
class _IndexedKeywordDocument:
    """Precomputed lexical fields for fast per-query scoring."""

    document: KeywordDocument
    term_frequency: Counter[str]
    length: int


def tokenize(text: str) -> list[str]:
    """Tokenize support-doc text for BM25 scoring."""
    return [token.lower() for token in _TOKEN_RE.findall(text)]


class InMemoryBM25KeywordSearchProvider:
    """Deterministic BM25 provider with precomputed lexical index.

    This implementation is still process-local, but it avoids per-query
    corpus tokenization and document-frequency scans. It is suitable for V1
    application-backed indexing until a Postgres FTS table is wired in Wave 3.
    """

    def __init__(self, documents: list[KeywordDocument] | None = None) -> None:
        """Initialize and precompute token frequencies/postings."""
        self._documents: list[_IndexedKeywordDocument] = []
        self._postings: dict[str, set[int]] = defaultdict(set)
        for doc in documents or []:
            tokens = tokenize(doc.text)
            indexed = _IndexedKeywordDocument(document=doc, term_frequency=Counter(tokens), length=len(tokens))
            doc_index = len(self._documents)
            self._documents.append(indexed)
            for term in indexed.term_frequency:
                self._postings[term].add(doc_index)

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
        query_terms = list(dict.fromkeys(tokenize(query_text)))
        if not query_terms:
            return []

        allowed_vis = set(visibility or ["public"])
        allowed_src = set(source_allowlist) if source_allowlist else None
        allowed_sv = set(source_version_ids) if source_version_ids else None
        candidate_ids = self._candidate_ids(query_terms)
        filtered_ids = [
            doc_id for doc_id in candidate_ids
            if self._matches_filters(
                self._documents[doc_id].document,
                tenant_id=tenant_id,
                allowed_vis=allowed_vis,
                allowed_src=allowed_src,
                allowed_sv=allowed_sv,
                locale=locale,
                active_only=active_only,
            )
        ]
        if not filtered_ids:
            return []

        filtered_set = set(filtered_ids)
        avg_len = sum(self._documents[doc_id].length for doc_id in filtered_ids) / len(filtered_ids)
        doc_frequency = {term: len(self._postings.get(term, set()) & filtered_set) for term in query_terms}

        results: list[KeywordResult] = []
        for doc_id in filtered_ids:
            indexed = self._documents[doc_id]
            score = _bm25_score(query_terms, indexed.term_frequency, indexed.length, len(filtered_ids), avg_len, doc_frequency)
            if score > 0:
                doc = indexed.document
                results.append(KeywordResult(doc.chunk_id, score, dict(doc.payload or {})))
        results.sort(key=lambda item: item.score, reverse=True)
        return results[:candidate_top_k]

    def _candidate_ids(self, query_terms: list[str]) -> set[int]:
        """Return docs containing at least one query term."""
        candidate_ids: set[int] = set()
        for term in query_terms:
            candidate_ids.update(self._postings.get(term, set()))
        return candidate_ids

    def _matches_filters(
        self,
        doc: KeywordDocument,
        *,
        tenant_id: UUID,
        allowed_vis: set[str],
        allowed_src: set[UUID] | None,
        allowed_sv: set[UUID] | None,
        locale: str | None,
        active_only: bool,
    ) -> bool:
        """Apply tenant and lifecycle filters before scoring."""
        return (
            doc.tenant_id == tenant_id
            and (not active_only or doc.is_active)
            and doc.visibility in allowed_vis
            and (locale is None or doc.locale == locale)
            and (allowed_src is None or doc.source_id in allowed_src)
            and (allowed_sv is None or doc.source_version_id in allowed_sv)
        )


def _bm25_score(
    query_terms: list[str],
    term_frequency: Counter[str],
    doc_len: int,
    corpus_size: int,
    avg_len: float,
    doc_frequency: dict[str, int],
) -> float:
    k1 = 1.5
    b = 0.75
    score = 0.0
    for term in query_terms:
        freq = term_frequency.get(term, 0)
        if freq == 0:
            continue
        containing = doc_frequency.get(term, 0)
        idf = math.log(1 + (corpus_size - containing + 0.5) / (containing + 0.5))
        denom = freq + k1 * (1 - b + b * max(doc_len, 1) / max(avg_len, 1.0))
        score += idf * (freq * (k1 + 1)) / denom
    return score
