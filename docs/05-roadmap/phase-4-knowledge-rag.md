# Phase 4: Knowledge And RAG

**Goal:** answer from approved tenant knowledge. Source type v1 = **Markdown upload** (Decision 10); backend = **Qdrant** (ADR-001).

## Scope (outline)

- Knowledge schema: sources/versions/documents/chunks/sync jobs/candidates/ingest audit.
- Markdown upload + deterministic parser/chunker (500 tokens / 50 overlap).
- `VectorSearchProvider` contract → `QdrantVectorProvider` impl.
- `rag.search` built-in capability (real, replace Phase 3 stub).
- Citation builder + refusal policy.
- Source version activation (no partial visibility).

## Pipeline

```text
upload .md/.zip -> raw blob -> source_version(parsing)
-> parse (split by header) -> documents -> chunks (citation metadata)
-> embed -> Qdrant upsert (payload: tenant_id, source/version, visibility, active)
-> verify sample query -> activate -> tombstone old (keep 30d)
```

Detail: [vector-and-rag-storage.md](../02-persistence/vector-and-rag-storage.md).

## Resource Guardrails

- Add env-configurable ingest batch size, embedding concurrency, Qdrant upsert batch size, and max active source syncs per tenant.
- Keep Qdrant container caps from Phase 0 unless benchmark data proves they are too low; raise `QDRANT_*_LIMIT` before changing retrieval behavior.
- Prefer payload/index settings that reduce memory pressure for cold metadata; tenant filter correctness remains the release gate.

## Exit Criteria

- [ ] Tenant A cannot retrieve Tenant B chunks (app-layer filter gate).
- [ ] Empty/stale/low-confidence retrieval refuses/escalates.
- [ ] Source update/delete/tombstone hides old chunks.
- [ ] Source version activation prevents partial sync visibility.
- [ ] Answers include citation metadata.

## Validation

```bash
pytest tests/rag            # tenant isolation, refusal, citation, activation
```

## Notes

- URL allowlist defer Phase 5 (reuse pipeline, replace input → markdown intermediate).
- GitBook/Drive defer (OAuth credential handles).
- Qdrant has no RLS → mandatory app-layer tenant filter is release gate.

## References

- [ADR-001 Vector Backend](../06-decisions/adr-001-vector-backend.md)
- [Vector And RAG Storage](../02-persistence/vector-and-rag-storage.md)
- [Eval Datasets (Phase 4 focus)](../04-observability/eval-datasets.md)
