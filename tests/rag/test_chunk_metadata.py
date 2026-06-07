# ruff: noqa
from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.knowledge.chunker import KnowledgeChunkDraft
from app.knowledge.metadata import build_lexical_text, enrich_chunk


def _draft() -> KnowledgeChunkDraft:
    return KnowledgeChunkDraft("doc.md", ("Root",), "Section: Root\n\nHello WORLD\n", 0, 3)


def test_enrich_chunk_populates_complete_metadata() -> None:
    tenant_id = uuid4()
    source_id = uuid4()
    version_id = uuid4()
    document_id = uuid4()

    chunk = enrich_chunk(
        _draft(),
        tenant_id=tenant_id,
        source_id=source_id,
        source_version_id=version_id,
        document_id=document_id,
        source_title="Guide",
        source_uri="s3://guide.md",
        visibility="private",
        locale="en",
    )

    assert chunk.tenant_id == tenant_id
    assert chunk.source_id == source_id
    assert chunk.source_version_id == version_id
    assert chunk.document_id == document_id
    assert chunk.source_title == "Guide"
    assert chunk.visibility == "private"
    assert chunk.locale == "en"
    assert chunk.lexical_text == "section: root hello world"
    assert not chunk.is_active


def test_content_hash_is_stable_and_tenant_specific() -> None:
    tenant_id = uuid4()
    args = dict(source_id=uuid4(), source_version_id=uuid4(), document_id=uuid4(), source_title="Guide")

    one = enrich_chunk(_draft(), tenant_id=tenant_id, **args)
    two = enrich_chunk(_draft(), tenant_id=tenant_id, **args)
    other_tenant = enrich_chunk(_draft(), tenant_id=uuid4(), **args)

    assert one.content_hash == two.content_hash
    assert one.content_hash != other_tenant.content_hash


def test_enrich_chunk_rejects_missing_or_zero_ids() -> None:
    with pytest.raises(ValueError):
        enrich_chunk(
            _draft(),
            tenant_id=UUID(int=0),
            source_id=uuid4(),
            source_version_id=uuid4(),
            document_id=uuid4(),
            source_title="Guide",
        )


def test_build_lexical_text_normalizes_whitespace_and_case() -> None:
    assert build_lexical_text(" Hello\n\tWORLD  ") == "hello world"
