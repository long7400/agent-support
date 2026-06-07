"""Chunk metadata enrichment helpers for knowledge ingestion."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from uuid import UUID

from app.knowledge.chunker import KnowledgeChunkDraft


@dataclass(frozen=True)
class EnrichedKnowledgeChunk:
    """Chunk text plus tenant-safe retrieval metadata."""

    tenant_id: UUID
    source_id: UUID
    source_version_id: UUID
    document_id: UUID
    document_path: str
    source_uri: str | None
    source_title: str
    section_path: tuple[str, ...]
    visibility: str
    locale: str | None
    ordinal: int
    token_count: int
    text: str
    lexical_text: str
    content_hash: str
    is_active: bool = False


def enrich_chunk(
    draft: KnowledgeChunkDraft,
    *,
    tenant_id: UUID,
    source_id: UUID,
    source_version_id: UUID,
    document_id: UUID,
    source_title: str,
    source_uri: str | None = None,
    visibility: str = "public",
    locale: str | None = None,
    is_active: bool = False,
) -> EnrichedKnowledgeChunk:
    """Attach stable metadata to a chunk draft."""
    for name, value in {
        "tenant_id": tenant_id,
        "source_id": source_id,
        "source_version_id": source_version_id,
        "document_id": document_id,
    }.items():
        if value is None or value == UUID(int=0):
            raise ValueError(f"{name} must not be None or zero")
    lexical = build_lexical_text(draft.text)
    digest = hashlib.sha256(
        "|".join(
            [
                str(tenant_id),
                str(source_id),
                str(source_version_id),
                str(document_id),
                str(draft.ordinal),
                draft.text,
            ]
        ).encode("utf-8")
    ).hexdigest()
    return EnrichedKnowledgeChunk(
        tenant_id=tenant_id,
        source_id=source_id,
        source_version_id=source_version_id,
        document_id=document_id,
        document_path=draft.document_path,
        source_uri=source_uri,
        source_title=source_title,
        section_path=draft.section_path,
        visibility=visibility,
        locale=locale,
        ordinal=draft.ordinal,
        token_count=draft.token_count,
        text=draft.text,
        lexical_text=lexical,
        content_hash=digest,
        is_active=is_active,
    )


def build_lexical_text(text: str) -> str:
    """Normalize chunk text for deterministic lexical indexing."""
    return re.sub(r"\s+", " ", text.lower()).strip()
