"""Cache-key helpers for the retrieval layer.

Keys are deterministic strings composed from the parameters that affect
cacheability.  Tenants, source versions, and retrieval modes each produce
different keys even when all other parameters are identical.
"""

from __future__ import annotations

import hashlib
from typing import Any
from uuid import UUID

from app.vector.models import RetrievalMode


def _hex_hash(value: str) -> str:
    """Return a short hex digest of a string."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _fmt_uuids(ids: list[UUID] | None) -> str:
    """Format an optional list of UUIDs into a sorted canonical string."""
    if not ids:
        return ""
    return ",".join(str(u) for u in sorted(ids))


def build_embedding_cache_key(
    tenant_id: UUID,
    text: str,
    embedding_model: str,
    embedding_version: str = "",
) -> str:
    """Build a deterministic cache key for an embedding result.

    Args:
        tenant_id: Tenant scope.
        text: Input text that was embedded.
        embedding_model: Embedding model name (e.g. ``text-embedding-3-small``).
        embedding_version: Optional model version string.

    Returns:
        Cache key string.
    """
    text_hash = _hex_hash(text)
    parts: list[tuple[str, Any]] = [
        ("tenant", str(tenant_id)),
        ("text_hash", text_hash),
        ("model", embedding_model),
        ("version", embedding_version),
    ]
    inner = ":".join(f"{k}={v}" for k, v in parts)
    return f"emb:{_hex_hash(inner)}"


def build_retrieval_cache_key(
    tenant_id: UUID,
    query_text: str,
    retrieval_mode: RetrievalMode,
    source_version_ids: list[UUID] | None = None,
    visibility: list[str] | None = None,
    locale: str | None = None,
    embedding_model: str = "",
    candidate_top_k: int = 50,
    final_top_k: int = 10,
    min_score: float = 0.0,
) -> str:
    """Build a deterministic cache key for a retrieval result.

    Two queries from different tenants or with different retrieval modes
    or source version lists always produce different keys.

    Args:
        tenant_id: Tenant scope.
        query_text: Raw query text.
        retrieval_mode: Search mode (hybrid, vector, keyword).
        source_version_ids: Optional source version scope.
        visibility: Allowed visibility levels.
        locale: Optional locale filter.
        embedding_model: Embedding model used.
        candidate_top_k: Raw candidate count.
        final_top_k: Final result count.
        min_score: Minimum score threshold.

    Returns:
        Cache key string.
    """
    query_hash = _hex_hash(query_text)
    vis_str = ",".join(sorted(visibility or ["public"]))
    loc_str = locale or ""
    sv_str = _fmt_uuids(source_version_ids)

    parts: list[tuple[str, Any]] = [
        ("tenant", str(tenant_id)),
        ("mode", retrieval_mode.value),
        ("qhash", query_hash),
        ("sv", sv_str),
        ("vis", vis_str),
        ("locale", loc_str),
        ("model", embedding_model),
        ("ck", str(candidate_top_k)),
        ("fk", str(final_top_k)),
        ("mins", f"{min_score:.4f}"),
    ]
    inner = ":".join(f"{k}={v}" for k, v in parts)
    return f"ret:{_hex_hash(inner)}"
