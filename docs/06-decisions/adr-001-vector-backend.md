# ADR-001: Vector Backend For RAG

- **Status:** accepted
- **Date:** 2026-06-01
- **Deciders:** eng-lead, ai-eng, security-reviewer
- **Related:** PRD-004, PRD-010, ADR-002, [vector-and-rag-storage.md](../02-persistence/vector-and-rag-storage.md)

## Context

Template có pgvector + mem0 sẵn. Docs design yêu cầu `VectorSearchProvider` contract trừu tượng để không khoá runtime vào backend cụ thể. Cần chọn backend v1 sau contract đó. Multi-tenant SaaS từ đầu, 10-100 tenants dự kiến.

## Decision

**Qdrant ngay v1, sau `VectorSearchProvider` contract.** Graph chỉ depend vào Protocol, không Qdrant client trực tiếp.

## Consequences

### Positive
- Filter payload nhanh, scale tốt cho >1M chunks, dedicated vector ops.
- Provider contract giữ runtime lock-free — swap backend không sửa graph.

### Negative / Costs
- Thêm 1 stateful service vào docker-compose (backup/restore riêng, RAM trên VPS).
- **Qdrant không có RLS** → tenant isolation enforce hoàn toàn ở app layer.
- Memory pressure trên single VPS (Qdrant + Langfuse Clickhouse cùng host).

### Follow-up actions
- Thêm qdrant vào docker-compose (Phase 0).
- `VectorSearchProvider.search()` raise nếu `tenant_id` empty.
- Cross-tenant vector denial test = release gate (Phase 4).
- Qdrant snapshot weekly off-site backup.

## Alternatives Considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| pgvector only v1 | Có sẵn, 1 DB, RLS đơn giản, ít moving parts | Hiệu năng kém >1M chunks/tenant, vector ops cạnh tranh CPU OLTP | rejected |
| Provider contract + pgvector v1, Qdrant later | MVP nhanh, swap khi scale | Phải migrate sau khi scale | rejected (user prefer Qdrant ngay) |
| **Qdrant ngay v1** | Scale + filter tốt từ đầu | App-layer isolation, extra service | **chosen** |

## Notes

Migration trigger sang dedicated/managed Qdrant: 1 tenant ~500K chunks hoặc query p95 vượt SLO. Single collection + payload filter cho 10-100 tenants; per-tenant collection chỉ khi enterprise isolation yêu cầu.
