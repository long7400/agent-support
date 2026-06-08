# ADR-002: Tenant Isolation Model

- **Status:** accepted
- **Date:** 2026-06-01
- **Deciders:** eng-lead, security-reviewer, db-eng
- **Related:** PRD-001, PRD-002, ADR-004, [migration-rules.md](../02-persistence/migration-rules.md), research report `plans/reports/from-researcher-to-brainstormer-260601-0002-multi-tenant-postgres-isolation-report.md`

## Context

PostgreSQL chứa tenant config, chat events, agent runs, knowledge metadata, audit, tools. PRD-002 yêu cầu RLS hoặc equivalent. Multi-tenant SaaS từ đầu → cross-tenant leak là rủi ro #1. Research report xác nhận RLS là isolation mechanism duy nhất chặn accidental cross-tenant query ở DB layer.

## Decision

**PostgreSQL RLS toàn diện cho mọi tenant-owned table**, với `SET LOCAL app.current_tenant` per-request transaction, app role không phải owner (no BYPASSRLS), và operator role riêng có BYPASSRLS cho incident response.

## Consequences

### Positive
- DB-enforced: miss query predicate = denied, không leak.
- Sec reviewer + compliance OK (Supabase pattern, industry standard).
- Cross-tenant denial test chạy ở DB level.

### Negative / Costs
- Mọi request phải mở transaction + set context.
- LangGraph checkpointer cần handle riêng (tenant_id trong metadata + app-side filter).
- pgbouncer (nếu dùng) phải session-pool mode.
- Operator query phải qua role riêng + audit.

### Follow-up actions
- Helper `with_tenant_context()` (Phase 1): `async with db.begin()` + `SET LOCAL`.
- Alembic raw SQL cho RLS policies (`ENABLE` + `FORCE` + `USING` + `WITH CHECK`).
- `app_user` (no BYPASSRLS) cho runtime; `app_operator` (BYPASSRLS) cho incident, audited.
- Cross-tenant denial test under `app_user` = release gate.
- `graph_checkpoint_metadata` table map thread_id → tenant_id.

## Alternatives Considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| **RLS toàn diện** | DB-enforced, catches missed predicate | Transaction friction, checkpointer handling | **chosen** |
| App-layer enforcement | Đơn giản, không đụng ORM | 1 query miss WHERE = leak; test denial khó tin | rejected |
| Schema-per-tenant | Mạnh nhất isolation | Migration N tenants, pool phức tạp, không scale | rejected |
| Hybrid (RLS hot tables) | Cân bằng risk/friction | Phải document table nào RLS; test ma trận phức | rejected |

## Notes

`SET LOCAL` BẮT BUỘC trong `async with db.begin()` — ngoài transaction = setting sống đến hết connection → leak qua pool. RLS với SQLAlchemy 2.0 async + asyncpg supported (ADR-004). Qdrant không có RLS → app-layer filter (ADR-001). Counter-argument (RLS sai nếu <5 tenants hoặc team thiếu PG expertise) không áp dụng ở đây.
