# Vector And RAG Storage

Qdrant contract + citation model cho source-backed RAG. Backend = Qdrant ngay v1 sau `VectorSearchProvider` contract (ADR-001).

## Why Qdrant (ADR-001)

Chốt Qdrant ngay v1 (không pgvector-first):
- Filter payload nhanh, scale tốt cho >1M chunks, dedicated vector ops.
- Trade-off chấp nhận: thêm 1 stateful service, backup/restore riêng, **tenant isolation enforce ở app layer** (Qdrant không có RLS).

`VectorSearchProvider` contract giữ runtime lock-free: đổi backend không sửa graph.

## VectorSearchProvider Contract

```python
class VectorSearchProvider(Protocol):
    async def upsert(self, points: list[VectorPoint]) -> None: ...
    async def search(self, query: VectorQuery) -> list[VectorHit]: ...
    async def delete(self, filter: VectorFilter) -> None: ...
    async def delete_collection(self, tenant_id: str) -> None: ...  # GDPR
```

```python
@dataclass
class VectorQuery:
    tenant_id: str                 # MANDATORY — enforce app-layer
    embedding: list[float]
    top_k: int
    active_only: bool = True
    visibility: list[str] = ("public",)
    source_allowlist: list[str] | None = None
    locale: str | None = None
```

Implementation v1: `QdrantVectorProvider`. Graph chỉ depend vào Protocol, không Qdrant client trực tiếp.

## Vector Payload Contract

Mọi point trong Qdrant mang payload đủ để filter + cite:

```json
{
  "tenant_id": "uuid",
  "source_id": "uuid",
  "source_version_id": "uuid",
  "document_id": "uuid",
  "chunk_id": "uuid",
  "visibility": "public|private|internal",
  "source_uri": "string",
  "source_title": "string",
  "section_path": ["string"],
  "locale": "en",
  "content_hash": "sha256",
  "active": true,
  "updated_at": "timestamp"
}
```

## Tenant Isolation (App-Layer — CRITICAL)

Qdrant không có RLS. Isolation hoàn toàn ở app layer:

- **Mọi** `search()` BẮT BUỘC có `tenant_id` filter trong Qdrant `Filter.must`. Query thiếu tenant filter = bug, fail closed.
- `VectorSearchProvider.search()` raise nếu `tenant_id` empty.
- Collection strategy: **single collection + payload filter** (10-100 tenants). Per-tenant collection chỉ khi enterprise isolation yêu cầu (migration trigger).
- Cross-tenant denial test là **release gate**: query tenant A embedding với tenant B filter → 0 hits.

Qdrant filter example:
```python
Filter(must=[
    FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id)),
    FieldCondition(key="active", match=MatchValue(value=True)),
    FieldCondition(key="visibility", match=MatchAny(any=visibility_allowed)),
])
```

## Retrieval Filter Requirements

Retrieval phải filter theo:
- tenant id (mandatory),
- active source version,
- visibility allowed cho current channel/user/policy (public channel không lấy private/internal trừ policy),
- optional source allowlist,
- optional locale,
- exclude deleted/tombstoned.

## Source Activation Strategy

PostgreSQL owns metadata + activation; Qdrant owns retrieval payload.

```text
1. Create immutable source version (knowledge_source_versions, status=parsing).
2. Parse/chunk/embed dưới source version đó.
3. Upsert Qdrant points với source_version payload (active=false ban đầu).
4. Verify counts + sample retrieval qua provider.
5. UPDATE source_version status=active (PostgreSQL) + set chunk active=true.
6. Query path dùng active version list từ PostgreSQL.
7. Tombstone old version → set active=false; giữ vectors 30d cho rollback, sau đó hard delete.
```

Partial sync không bao giờ visible (active=false cho đến khi verify pass).

## Knowledge Sync Lifecycle

```text
source_registered -> sync_requested -> fetch_started -> normalized
-> chunked -> embedded -> vector_upserted -> verified -> source_version_active
```

Failure states: fetch_failed, parse_failed, secret/PII_blocked, embed_failed, vector_write_failed, partial_verification_failed, stale/tombstoned.

## Markdown Pipeline (V1, Phase 4)

```text
admin upload .md/.zip -> raw blob (object storage)
-> parser: split by header (##, ###) -> documents
-> chunker: 500 tokens / 50 overlap (configurable per source), preserve header context
-> citation metadata: source_id, version_id, doc_id, section_path, chunk_id
-> embed -> vector
-> Qdrant upsert (payload above)
-> verify sample query -> activate
```

Visibility default: `public` (community Q&A). `private`/`internal` future. Parser deterministic, không invent facts.

URL allowlist (Phase 5) reuse pipeline: chỉ replace "raw input → markdown intermediate" step.

## Citation Builder

Answer source-backed phải kèm citation từ payload:
```json
{
  "source_title": "Tokenomics v2",
  "section_path": ["Vesting", "Team Allocation"],
  "source_uri": "uploaded://tokenomics-v2.md",
  "source_version_id": "uuid"
}
```

Refusal policy: empty retrieval / low confidence / stale version → refuse hoặc escalate, không synthesize confident answer.

## GDPR / Tenant Deletion

Khi tenant `deleting`: `VectorSearchProvider.delete_collection(tenant_id)` hoặc delete-by-filter `tenant_id` → xóa toàn bộ vectors. Phối hợp với hard delete PostgreSQL + Langfuse project (xem [persistence-strategy.md](persistence-strategy.md)).

## Backup

Qdrant snapshot weekly → off-site (B2/Storage Box). PostgreSQL metadata daily. Khi restore: PostgreSQL metadata + Qdrant snapshot phải cùng point-in-time (content_hash reconcile nếu drift).

## Operations Note

- Qdrant thêm vào docker-compose (ADR-008 single VPS).
- Memory: Qdrant + Langfuse Clickhouse cùng VPS → watch RAM (CX22 4GB tight).
- Migration trigger sang dedicated/managed: 1 tenant ~500K chunks hoặc query p95 vượt SLO.

## References

- [ADR-001 Vector Backend](../06-decisions/adr-001-vector-backend.md)
- [Persistence Strategy](persistence-strategy.md)
- [Schema Reference](schema-reference.md)
- [Core Agent Design](../01-architecture/core-agent-design.md)
- [Phase 4 Knowledge RAG](../05-roadmap/phase-4-knowledge-rag.md)
