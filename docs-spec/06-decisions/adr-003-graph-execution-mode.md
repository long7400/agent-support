# ADR-003: Graph Execution Mode

- **Status:** accepted
- **Date:** 2026-06-01
- **Deciders:** eng-lead, backend-eng, ai-eng
- **Related:** PRD-003, SLO (adapter ingest <= 500ms), [adapters-and-integrations.md](../01-architecture/adapters-and-integrations.md)

## Context

Khi adapter ingest event, graph chạy luôn trong HTTP request hay đẩy vào queue cho worker? SLO yêu cầu adapter ingest p95 <= 500ms **excluding graph work** → graph KHÔNG được nằm trong ingest path. Telegram webhook retry nếu reply chậm → duplicate. Cần durable event + idempotency cho replay/incident.

## Decision

**PostgreSQL outbox + polling worker với `FOR UPDATE SKIP LOCKED`**, kèm LISTEN/NOTIFY wake-up hybrid cho low latency. Redis chỉ dùng cache/rate-limit, KHÔNG làm outbox.

## Consequences

### Positive
- Same-DB transaction với `chat_events` → exactly-once, không drift.
- `SKIP LOCKED` cho horizontal scale (nhiều worker).
- Infra tối thiểu (chỉ Postgres), debug bằng SQL, RLS-friendly (outbox có tenant_id).
- Crash recovery qua AsyncPostgresSaver checkpoint + stale row reclaim.

### Negative / Costs
- Polling latency 1-2s nếu interval 1s (acceptable cho chat, không realtime <100ms).
- DB load tăng nhẹ với nhiều worker polling — mitigate bằng LISTEN/NOTIFY + partial index.
- 2 process (api + worker), debug phức tạp hơn sync.

### Follow-up actions
- `processing_outbox` + `delivery_outbox` schema với status/retries/dead_letter (Phase 2).
- Partial index `(status, run_after_ts, id) WHERE status='pending'`.
- Idempotency UNIQUE `(tenant_id, platform, external_message_id)`.
- Worker heartbeat + worker_id cho stale reclaim.
- LISTEN channel `outbox_new` + poll fallback 5s.

## Alternatives Considered

| Option | Verdict | Lý do |
| --- | --- | --- |
| Sync trong request | rejected | Vi phạm SLO; mất run khi restart; no retry. |
| Celery | rejected | Sync-first, async rough 2025, overkill. |
| arq / Dramatiq (Redis) | rejected | Split storage (Postgres + Redis), 2-step commit drift risk. |
| Kafka + faust | rejected | Overkill 10-100 tenants, heavy infra. |
| Temporal | rejected | 1 cluster nữa cần ops; dùng khi >5 workflow chains. |
| LISTEN/NOTIFY only | partial | Connection limit ~100, cần polling fallback. |
| **Postgres outbox + polling (SKIP LOCKED)** | **chosen** | Exactly-once, no extra infra, scale, RLS-friendly. |

## Notes

Migration path: nếu >10K events/sec hoặc multi-region → swap Kafka, giữ outbox abstraction consumer interface. Per-tenant fairness: `ORDER BY (tenant_id, id)` hoặc partition queue per tier nếu workload không đều.
