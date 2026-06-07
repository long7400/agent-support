"""In-memory knowledge source lifecycle orchestration for Phase 4 tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4, uuid5, NAMESPACE_URL

from app.knowledge.chunker import chunk_document
from app.knowledge.markdown_parser import extract_markdown_text, extract_markdown_zip
from app.infra.observability import record_rag_observability_event
from app.knowledge.metadata import enrich_chunk
from app.vector.fake import (
    FakeEmbeddingProvider,
    FakeKeywordSearchProvider,
    FakeVectorSearchProvider,
    _IndexedKeyword,
    _IndexedVector,
)


@dataclass
class KnowledgeSourceVersionRecord:
    """Mutable source-version state for local indexing tests."""

    id: UUID
    source_id: UUID
    tenant_id: UUID
    status: str = "queued"
    is_active: bool = False
    chunks: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class KnowledgeSyncJobRecord:
    """Mutable sync-job state with progress counters."""

    id: UUID
    tenant_id: UUID
    source_id: UUID
    source_version_id: UUID
    idempotency_key: str
    raw_content: str | bytes
    filename: str = "source.md"
    status: str = "queued"
    documents_processed: int = 0
    chunks_embedded: int = 0
    vectors_upserted: int = 0
    lexical_indexed: int = 0
    errors: list[str] = field(default_factory=list)
    started_at: datetime | None = None
    completed_at: datetime | None = None


class InMemoryKnowledgeIngestService:
    """Small deterministic ingest service used by tests and local harness wiring."""

    def __init__(self, embedding_provider: FakeEmbeddingProvider | None = None) -> None:
        """Create empty indexes and optional deterministic embedding provider."""
        self.embedding_provider = embedding_provider or FakeEmbeddingProvider(dimension=16)
        self.vector_index: list[_IndexedVector] = []
        self.keyword_index: list[_IndexedKeyword] = []
        self.versions: dict[UUID, KnowledgeSourceVersionRecord] = {}
        self.jobs: dict[UUID, KnowledgeSyncJobRecord] = {}
        self._idempotency: dict[tuple[UUID, str], UUID] = {}

    def create_job(
        self,
        *,
        tenant_id: UUID,
        source_id: UUID,
        raw_content: str | bytes,
        idempotency_key: str,
        filename: str = "source.md",
    ) -> KnowledgeSyncJobRecord:
        """Create or return an idempotent queued indexing job."""
        existing = self._idempotency.get((tenant_id, idempotency_key))
        if existing is not None:
            return self.jobs[existing]
        version = KnowledgeSourceVersionRecord(id=uuid4(), source_id=source_id, tenant_id=tenant_id)
        self.versions[version.id] = version
        job = KnowledgeSyncJobRecord(
            id=uuid4(),
            tenant_id=tenant_id,
            source_id=source_id,
            source_version_id=version.id,
            idempotency_key=idempotency_key,
            raw_content=raw_content,
            filename=filename,
        )
        self.jobs[job.id] = job
        self._idempotency[(tenant_id, idempotency_key)] = job.id
        return job

    async def index_job(self, job_id: UUID) -> KnowledgeSyncJobRecord:
        """Run Markdown extraction, chunking, embedding, indexing, and activation."""
        job = self.jobs[job_id]
        version = self.versions[job.source_version_id]
        if job.status == "succeeded":
            return job
        job.status = "running"
        version.status = "parsing"
        job.started_at = datetime.now(UTC)
        try:
            docs = (
                extract_markdown_zip(job.raw_content)
                if isinstance(job.raw_content, bytes)
                else extract_markdown_text(job.raw_content, path=job.filename)
            )
            enriched: list[dict[str, Any]] = []
            for doc in docs:
                drafts = chunk_document(doc, target_tokens=500, overlap_tokens=50)
                document_id = uuid4()
                enriched.extend(
                    enrich_chunk(
                        draft,
                        tenant_id=job.tenant_id,
                        source_id=job.source_id,
                        source_version_id=job.source_version_id,
                        document_id=document_id,
                        source_uri=doc.path,
                        source_title=doc.title,
                    ).__dict__
                    for draft in drafts
                )
            embeddings = await self.embedding_provider.embed([c["text"] for c in enriched], job.tenant_id)
            self._replace_version_indexes(job, enriched, embeddings, active=False)
            version.chunks = enriched
            version.status = "active"
            version.is_active = True
            self._activate_version(job.tenant_id, job.source_id, job.source_version_id)
            job.documents_processed = len(docs)
            job.chunks_embedded = len(enriched)
            job.vectors_upserted = len(enriched)
            job.lexical_indexed = len(enriched)
            job.status = "succeeded"
            record_rag_observability_event(
                "rag.ingest.completed",
                tenant_id=str(job.tenant_id),
                source_id=str(job.source_id),
                source_version_id=str(job.source_version_id),
                job_id=str(job.id),
                status=job.status,
                documents_processed=job.documents_processed,
                chunks_embedded=job.chunks_embedded,
                vectors_upserted=job.vectors_upserted,
                lexical_indexed=job.lexical_indexed,
            )
        except Exception as exc:  # pragma: no cover - defensive state transition
            version.status = "failed"
            version.is_active = False
            job.status = "failed"
            job.errors.append(str(exc))
            record_rag_observability_event(
                "rag.ingest.failed",
                tenant_id=str(job.tenant_id),
                source_id=str(job.source_id),
                source_version_id=str(job.source_version_id),
                job_id=str(job.id),
                status=job.status,
            )
        finally:
            job.completed_at = datetime.now(UTC)
        return job

    def tombstone_source(self, *, tenant_id: UUID, source_id: UUID) -> None:
        """Hide all versions and indexed chunks for a source."""
        for version in self.versions.values():
            if version.tenant_id == tenant_id and version.source_id == source_id:
                version.status = "tombstoned"
                version.is_active = False
        for item in self.vector_index:
            if item.tenant_id == tenant_id and item.source_id == source_id:
                item.is_active = False
                item.payload["is_active"] = False
        for item in self.keyword_index:
            if item.tenant_id == tenant_id and item.source_id == source_id:
                item.is_active = False
                item.payload["is_active"] = False

    def vector_provider(self) -> FakeVectorSearchProvider:
        """Return a vector provider over the current in-memory index."""
        return FakeVectorSearchProvider(self.vector_index)

    def keyword_provider(self) -> FakeKeywordSearchProvider:
        """Return a keyword provider over the current in-memory index."""
        return FakeKeywordSearchProvider(self.keyword_index)

    def _replace_version_indexes(
        self, job: KnowledgeSyncJobRecord, chunks: list[dict[str, Any]], embeddings: list[list[float]], *, active: bool
    ) -> None:
        self.vector_index = [item for item in self.vector_index if item.source_version_id != job.source_version_id]
        self.keyword_index = [item for item in self.keyword_index if item.source_version_id != job.source_version_id]
        for chunk, embedding in zip(chunks, embeddings, strict=True):
            payload = dict(chunk)
            chunk_id = UUID(str(payload.get("chunk_id") or uuid5(NAMESPACE_URL, str(chunk["content_hash"]))))
            payload["chunk_id"] = str(chunk_id)
            payload["is_active"] = active
            self.vector_index.append(
                _IndexedVector(
                    chunk_id,
                    job.tenant_id,
                    embedding,
                    chunk["text"],
                    chunk["visibility"],
                    chunk.get("locale"),
                    active,
                    job.source_version_id,
                    job.source_id,
                    payload,
                )
            )
            self.keyword_index.append(
                _IndexedKeyword(
                    chunk_id,
                    job.tenant_id,
                    chunk["lexical_text"],
                    chunk["visibility"],
                    chunk.get("locale"),
                    active,
                    job.source_version_id,
                    job.source_id,
                    payload,
                )
            )

    def _activate_version(self, tenant_id: UUID, source_id: UUID, active_version_id: UUID) -> None:
        for version in self.versions.values():
            if version.tenant_id == tenant_id and version.source_id == source_id and version.id != active_version_id:
                version.status = "tombstoned"
                version.is_active = False
        for item in [*self.vector_index, *self.keyword_index]:
            if item.tenant_id == tenant_id and item.source_id == source_id:
                item.is_active = item.source_version_id == active_version_id
                item.payload["is_active"] = item.is_active
