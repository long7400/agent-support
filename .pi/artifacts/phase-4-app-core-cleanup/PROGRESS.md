
### Task 1: Rename app/core to app/infra — ✓

**Files changed:**
- `app/infra/**`: moved shared infrastructure modules from `app/core`.
- `app/core/**`: removed legacy infrastructure package and `langgraph` compatibility surface.
- `app/**`, `tests/**`, `alembic/env.py`: migrated imports to `app.infra.*`.
- `app/infra/README.md`: documented infrastructure boundary.
- `app/agent_harness/README.md`: documented harness boundary.

**Verification:**
- `rg -n "app\\.core|core\\.langgraph|LangGraphAgent" app tests alembic || true` → exit 0, no matches.
- `uv run ruff check app tests` → exit 0, all checks passed.
- `uv run pytest tests/agent_harness tests/outbox tests/adapter tests/test_p0_infra.py` → exit 0, 212 passed.

**Notes:**
- Harness implemented Wave 0 partially, then manual cleanup completed remaining import migration and verification.
- Pre-existing untracked `docs/rag-sheed.md` was left untouched and unstaged.

---

### Wave 1: Knowledge Persistence & Retrieval Contracts — ✓

**Sprint 1: Knowledge Persistence Schema — PASS**
12 criteria, 49 tests.

**Files created:**
- `app/models/knowledge_source.py` — KnowledgeSource model
- `app/models/knowledge_source_version.py` — KnowledgeSourceVersion model
- `app/models/knowledge_document.py` — KnowledgeDocument model
- `app/models/knowledge_chunk.py` — KnowledgeChunk model
- `app/models/knowledge_sync_job.py` — KnowledgeSyncJob model
- `app/models/knowledge_ingest_audit.py` — KnowledgeIngestAudit model
- `alembic/versions/c5e7a9b1d3f4_p4_knowledge_persistence.py` — migration (down_revision=b4f6d9c1e23f)
- `tests/rag/test_knowledge_schema.py` — 49 tests

**Schema summary:**
- 6 tenant-owned tables with RLS policies, all with `tenant_id` FK + index
- KnowledgeChunk: compound indexes on `(tenant_id, source_id)` and `(tenant_id, source_version_id, is_active)`
- KnowledgeSyncJob: unique constraint on `(tenant_id, idempotency_key)`
- CheckConstraints on `source_type`, `status`, `default_visibility`, `visibility` across models
- Migration round-trip verified: upgrade head → downgrade -1 → upgrade head

**Verification:**
- `alembic upgrade head` → exit 0
- `alembic downgrade -1` → exit 0
- `pytest tests/rag/test_knowledge_schema.py -v` → 49 passed
- `ruff check` → all checks passed

---

**Sprint 2: Retrieval Contracts, Fake Providers, Query Rewrite, And Cache Keys — PASS**
27 criteria, 81 tests.

**Files created:**
- `app/vector/__init__.py` — vector package init with exports
- `app/vector/contracts.py` — EmbeddingProvider, VectorSearchProvider, KeywordSearchProvider, HybridRetriever, Reranker protocols + VectorResult, KeywordResult, RerankedResult dataclasses
- `app/vector/models.py` — RetrievalMode enum, RetrievalQuery Pydantic model
- `app/vector/fake.py` — FakeEmbeddingProvider, FakeVectorSearchProvider, FakeKeywordSearchProvider, FakeHybridRetriever, FakeReranker
- `app/knowledge/__init__.py` — knowledge package init with exports
- `app/knowledge/contracts.py` — QueryRewriter protocol
- `app/knowledge/query_rewrite.py` — DeterministicQueryRewriter
- `app/knowledge/cache.py` — build_embedding_cache_key, build_retrieval_cache_key
- `tests/rag/test_retrieval_contracts.py` — 46 tests
- `tests/rag/test_query_rewrite_and_cache_keys.py` — 35 tests

**Contract summary:**
- 6 protocols in `app/vector/contracts.py`: EmbeddingProvider, VectorSearchProvider, KeywordSearchProvider, HybridRetriever, Reranker
- 3 response dataclasses: VectorResult, KeywordResult, RerankedResult
- RetrievalMode enum (`hybrid`, `vector`, `keyword`), RetrievalQuery Pydantic model in `app/vector/models.py`
- 5 fake implementations in `app/vector/fake.py`: deterministic embedding (SHA-256), in-memory vector/keyword search, RRF fusion hybrid retriever, min_score reranker
- QueryRewriter protocol + DeterministicQueryRewriter in `app/knowledge/`
- Cache key helpers in `app/knowledge/cache.py` with tenant/source-version/mode uniqueness guarantees
- All providers fail-closed on empty/None tenant_id
- Zero Qdrant imports in contract files (only docstring mentions)

**Verification:**
- `ruff check app/vector/ app/knowledge/` → all checks passed
- `pyright app/vector/ app/knowledge/` → 0 errors, 0 warnings
- `pytest tests/rag/test_retrieval_contracts.py` → 46 passed
- `pytest tests/rag/test_query_rewrite_and_cache_keys.py` → 35 passed
- `pytest tests/rag/` → 130 passed (49 existing + 81 new)

---

### Wave 2: Markdown Pipeline, Dense Provider, Lexical Provider, Hybrid Fusion — ✓

**Files changed:**
- `app/knowledge/markdown_parser.py`: deterministic Markdown text/ZIP extraction, normalization, heading section parser.
- `app/knowledge/chunker.py`: section-aware deterministic chunk drafts with token target/overlap.
- `app/knowledge/metadata.py`: enriched chunk metadata, lexical text, stable tenant/version-aware hashes.
- `app/vector/qdrant.py`: Qdrant vector provider and payload filter builder with mandatory tenant/active/visibility/source/version/locale filters.
- `app/knowledge/keyword_search.py`: deterministic in-memory BM25 keyword provider.
- `app/knowledge/retrieval.py`: RRF hybrid retriever combining vector and lexical branches with dedupe and final_top_k cap.
- `app/infra/config.py`: Qdrant collection/vector/batch/top-k settings.
- `app/knowledge/__init__.py`: updated exports for retrieval types.
- `tests/rag/test_markdown_chunking.py`, `tests/rag/test_chunk_metadata.py`, `tests/rag/test_qdrant_tenant_filter.py`, `tests/rag/test_hybrid_search.py`: Wave 2 coverage.

**Verification:**
- `uv run pytest tests/rag/test_markdown_chunking.py tests/rag/test_chunk_metadata.py tests/rag/test_qdrant_tenant_filter.py tests/rag/test_hybrid_search.py` → exit 0, 18 passed.
- `uv run pytest tests/rag` → exit 0, 156 passed, 1 skipped.
- `uv run ruff check app tests` → exit 0, all checks passed.
- `uv run pyright app evals` → exit 0, 0 errors.

**Notes:**
- Harness tool was invoked twice but planner output was not accepted by the harness, so Wave 2 was completed directly in-session afterward.
- No Wave 3+ lifecycle, `rag.search`, prompt/citation/refusal, observability/eval, or memory policy work was implemented.
- Pre-existing untracked `docs/rag-sheed.md` remains untouched and unstaged.

---

### Wave 3: Source Lifecycle and `rag.search` Integration — ✓

**Files changed:**
- `app/knowledge/ingest_service.py`: added deterministic in-memory lifecycle service for queued jobs, idempotent indexing, Markdown extraction, chunk enrichment, fake embedding/vector/keyword index updates, source-version activation, and tombstone hiding.
- `app/agent_harness/capabilities/rag_search.py`: added tenant-scoped `rag.search` capability returning bounded hybrid snippets, citations, audit metadata, and typed refusals.
- `app/agent_harness/capabilities/registry.py`: registered `rag.search` and passed harness tenant context into the capability.
- `.pi/artifacts/phase-4-app-core-cleanup/RUN-REPORT.md`: updated with Wave 3 evidence.
- `.pi/artifacts/phase-4-app-core-cleanup/PROGRESS.md`: recorded Wave 3 completion.

**Verification:**
- `uv run ruff check app/knowledge/ingest_service.py app/agent_harness/capabilities/rag_search.py app/agent_harness/capabilities/registry.py` → exit 0, all checks passed.
- `uv run pyright app/knowledge/ingest_service.py app/agent_harness/capabilities/rag_search.py app/agent_harness/capabilities/registry.py` → exit 0, 0 errors, 0 warnings.
- `uv run pytest tests/rag tests/agent_harness` → exit 0, 222 passed, 1 skipped.

**Notes:**
- Harness tool was invoked for Wave 3 but returned `clean — nothing to commit`; scoped Wave 3 implementation was completed directly afterward.
- Pre-existing untracked `docs/rag-sheed.md` remains untouched and unstaged.
- Production DB/Celery-backed source lifecycle remains a broader Phase 4 hardening target; this wave adds deterministic local lifecycle and harness capability wiring.

---

### Sprint 1: Prompt Evidence, Citations, And Refusal Policy — ✓

**Files changed:**
- `app/agent_harness/capabilities/rag_search.py`: bounded final snippets/citations, output-size caps, and typed missing/denied/no-results/stale/below-threshold refusal behavior.
- `app/agent_harness/middleware/dynamic_prompt.py`: prompt-visible RAG source text is rendered only as delimited untrusted evidence with source/version/chunk citation metadata.
- `app/agent_harness/middleware/tool_guard.py`: `rag.search` validation now allows the retrieval/citation/refusal arguments used by the real capability path.
- `tests/rag/test_prompt_visible_snippets.py`: bounded cited evidence prompt coverage.
- `tests/rag/test_source_prompt_injection.py`: source prompt-injection quarantine fixture coverage.
- `tests/rag/test_citations_and_refusals.py`: citation, no-results, stale, denied, low-confidence, and output-bound refusal coverage.

**Verification:**
- `uv run pytest tests/rag/test_prompt_visible_snippets.py tests/rag/test_source_prompt_injection.py tests/rag/test_citations_and_refusals.py tests/agent_harness/test_middleware_order.py` → exit 0, 18 passed.
- `uv run ruff check app tests` → exit 0, all checks passed.
- `uv run pyright app evals` → exit 0, 0 errors, 0 warnings.

**Notes:**
- Evidence text remains inside the system prompt only as explicitly delimited, untrusted source evidence; it is not promoted into system/developer/tool instructions.
- Final snippets are capped by `final_top_k`, per-snippet character limits, and aggregate prompt/tool-output size limits.

### Sprint 3: Memory Retrieval Policy Filters - done

**Files changed:**
- `app/models/long_term_memory.py`: added policy metadata helpers for fail-closed tenant/user/scope/visibility context and active-result filtering.
- `app/services/memory.py`: long-term memory search now requires tenant, user, scope, and visibility context; filters mem0 results by tenant, user, scope, visibility, and active status before formatting output.
- `tests/memory/test_memory_policy.py`: added disabled-path, missing-context, and full policy-filter unit coverage.

**Verification:**
- `uv run pytest tests/memory/test_memory_policy.py` -> exit 0, 6 passed.
- `uv run ruff check app/models/long_term_memory.py app/services/memory.py tests/memory/test_memory_policy.py` -> exit 0, all checks passed.
- `uv run pyright app/models/long_term_memory.py app/services/memory.py tests/memory/test_memory_policy.py` -> exit 0, 0 errors, 0 warnings.

**Notes:**
- Memory retrieval remains disabled by default; disabled retrieval denies safely without touching the backend.
- This sprint does not expose Qdrant or add any model/graph/middleware direct retrieval path; scoped memory access remains inside `app.services.memory`.

---

### Sprint 4: Final Regression, Diff Review, And Scoped Commit - PASS

**Completed work:**
- Refreshed final run artifacts with status, commands, results, goal-backward checks, changed files, and diff-review findings.
- Ran full scoped regression for RAG, harness, outbox, adapter, memory, ruff, and pyright.
- Re-ran import-boundary grep and confirmed no active `app.core`, `core.langgraph`, or `LangGraphAgent` references under `app`, `tests`, or `alembic`.
- Reviewed `git status --porcelain`, scoped `git diff --stat`, and scoped `git diff` before staging.
- Prepared scoped commit using explicit `git add <path>` paths only; no `git add .` used and no PR created.

**Verification:**
- `uv run pytest tests/rag tests/agent_harness tests/outbox tests/adapter tests/memory` -> exit 0, 383 passed, 1 skipped.
- `uv run ruff check app tests` -> exit 0, all checks passed.
- `uv run pyright app evals` -> exit 0, 0 errors, 0 warnings.
- `rg -n "app\\.core|core\\.langgraph|LangGraphAgent" app tests alembic || true` -> exit 0, no matches.

**Deferred non-scope hardening:**
- Production DB/Celery/Qdrant implementations for the deterministic local RAG lifecycle remain deferred to later lifecycle hardening.
- Pre-existing untracked `docs/rag-sheed.md` remains untouched and unstaged because it is outside the owned Sprint 4 scope.
