---
title: Agent Support Rebuild — Brainstorm Summary (13 Decisions)
date: 2026-06-01
status: design-approved
source: discuss.md
audience: founder, eng-lead, backend, ai-eng, security-reviewer, operator
---

# Brainstorm Summary — Agent Support Rebuild

## Problem Statement

Rebuild Agent Support (community-ops control plane cho nhiều dự án crypto) trên nền FastAPI + LangGraph template. Multi-tenant SaaS từ đầu. Ưu tiên tenant isolation, auditability, replayability, security, observability hơn tốc độ demo. Trước khi viết docs chi tiết + code, phải resolve 13 open questions về kiến trúc/persistence/security/ops vì chúng định hình mọi file sau.

## Scope

- **In scope:** Chốt 13 foundational/operational decisions + lock cấu trúc `docs/` mới (8 numbered folders + ADR records).
- **Out of scope (round này):** Implementation code, scaffolding, migration thực, CI wiring. Đó là việc của `/ck:plan` + phase docs.

## Non-Negotiable Constraints

- Multi-tenant SaaS từ ngày đầu — cross-tenant leak là rủi ro #1.
- Tái dùng template (FastAPI, LangGraph, Alembic, Langfuse, Prometheus/Grafana, Docker) thay vì port code cũ.
- Solo/small team, cost-first → MVP phải chạy rẻ nhưng portable để lift sang managed khi scale.
- Mỗi doc <= 800 LOC (docs.maxLoc). Numbered folders = reading order.

## Decisions Resolved

| # | Decision | Resolution | ADR |
| --- | --- | --- | --- |
| 1 | Vector backend | Qdrant ngay v1, sau `VectorSearchProvider` contract | ADR-001 |
| 2 | Tenant isolation | PostgreSQL RLS toàn diện + `SET LOCAL` per-request tx + operator role `BYPASSRLS` | ADR-002 |
| 3 | Graph execution mode | Postgres outbox + polling worker (`FOR UPDATE SKIP LOCKED`) + LISTEN/NOTIFY wake-up | ADR-003 |
| 4 | ORM choice | SQLAlchemy 2.0 thuần + Pydantic v2 riêng; migrate template Phase 0 | ADR-004 |
| 5 | Tenant admin auth | JWT user (human) + service principals (automation) + `tenant_memberships` | ADR-005 |
| 6 | Secret manager | KMS envelope encryption + Postgres credential table sau `KMSProvider` interface | ADR-006 |
| 7 | Trace backend | Langfuse self-host (Docker Compose) + redaction callback | ADR-007 |
| 8 | Deployment v1 | Single VPS + Docker Compose + GCP Cloud KMS free tier; ADR ghi migrate trigger | ADR-008 |
| 9 | Telegram strategy | Per-tenant bot (tenant tạo qua BotFather) + webhook mode | ADR-009 |
| 10 | First knowledge source | Markdown upload Phase 4, URL allowlist Phase 5 | — (roadmap) |
| 11 | Discord priority | Defer Phase 7; adapter contract Discord-ready từ Phase 2 (mock test) | — (roadmap) |
| 12 | Moderation review UI | Telegram bot review + minimal API Phase 6; web UI defer Phase 7+ | — (roadmap) |
| 13 | Retention policy | 90d chat / 180d runs / 30d model_calls / 2y audit / 1y moderation / 30d tombstone / 7d outbox + per-tenant override + GDPR <30d | — (persistence) |

## Key Rationale (compact)

- **D1 Qdrant:** Filter payload nhanh, scale tốt. Trade-off: external service, tenant isolation enforce ở app layer (Qdrant không có RLS), backup riêng, cần thêm vào docker-compose. Provider contract giữ runtime lock-free.
- **D2 RLS:** DB-enforced, miss predicate = denied chứ không leak. `SET LOCAL app.current_tenant` BẮT BUỘC trong `async with db.begin()` (ngoài tx = leak qua pool). pgbouncer phải session-pool mode. LangGraph checkpointer set tenant context riêng (include `tenant_id` trong checkpoint metadata + filter app-side). Operator role `BYPASSRLS` + audit mọi truy cập.
- **D3 Outbox:** SLO ingest p95 <= 500ms excluding graph work → graph KHÔNG được nằm trong ingest path. Same-DB transaction với `chat_events` → exactly-once. `SKIP LOCKED` cho horizontal scale. Không infra extra. Polling 1-2s lag acceptable cho chat; LISTEN/NOTIFY hybrid cho low latency. Loại Celery/arq/Kafka/Temporal vì overkill/split-storage.
- **D4 SQLAlchemy 2.0:** RLS pattern production-grade không có cho SQLModel. ~15-20 bảng domain → mix 2 ORM = nợ kỹ thuật. Tách persistence model vs API DTO. Migrate Phase 0 (chỉ auth.py + session model chạm).
- **D5 Auth:** Audit `actor_type` cần phân biệt human admin vs machine. JWT user + `tenant_memberships(user_id, tenant_id, role)`; service principals (API keys) cho automation/CI. OAuth/SSO defer Phase 7.
- **D6 Secrets:** Envelope encryption — KMS master encrypt DEK, DEK encrypt secret, store ciphertext + dek_handle trong DB. Resolve = KMS decrypt DEK in-memory → decrypt → use → discard. `KMSProvider` interface: `LocalKMSProvider` (dev, reject in prod), `CloudKMSProvider` (GCP). Pre-flight fail-closed nếu prod detect local.
- **D7 Langfuse self-host:** Crypto tenant hỏi data residency → control. Giữ eval framework template. 1 project/tenant. Redaction callback trước flush (release gate). Internal `agent_runs`/`audit_events` là source of truth.
- **D8 VPS:** Solo + cost-first vs SaaS HA là tension thật → giải bằng portable design (Docker + env config + KMS interface). Hetzner/DO VPS, Docker Compose. GCP KMS direct (free tier 20K ops/month). Migrate trigger: >20 tenants / enterprise SLA / Postgres >50GB / VPS >70% capacity.
- **D9 Per-tenant bot:** Brand isolation là feature. Telegram rate-limit per-bot. Bot ban blast radius = 1 tenant. Token qua KMS (D6). Webhook `/v1/webhook/telegram/{tenant_id}` + secret_token verify.
- **D10 Markdown first:** Đơn giản nhất verify TẤT CẢ Phase 4 acceptance (isolation, version activation, citation, refusal). Parser deterministic. URL Phase 5 reuse pipeline.
- **D11 Discord defer:** Contract (`AdapterPrincipal`, `NormalizedInboundEvent`, `OutboundDeliveryEnvelope`) Discord-ready từ Phase 2, verify bằng paper-design mock. Promote sớm nếu >=30% prospects yêu cầu.
- **D12 Telegram review:** Phase 6 acceptance chỉ cần "review override works". Inline keyboard [Approve][Reject][Escalate] → callback verify HMAC + role → execute + audit. Web UI Phase 7+.
- **D13 Retention:** Daily `retention_sweeper` cron. `audit_events` NEVER auto-delete. Per-tenant `retention_policy_json` với floor enforce (audit >= 90d). Partitioning by month defer Phase 7.

## Approved docs/ Structure

```
docs/
├── README.md                  # index + reading order
├── 00-foundation/             # brief, PRD, glossary, principles
├── 01-architecture/           # system, domain/tenant, agent, adapters, data-flow
├── 02-persistence/            # strategy, schema, migration rules, vector/rag
├── 03-security/               # threat model, controls, authn/z, secrets
├── 04-observability/          # obs+eval+ops, metrics, runbooks, eval datasets
├── 05-roadmap/                # rebuild roadmap + phase-0..7 deep/outline
├── 06-decisions/              # ADR-001..009 + template
├── 07-onboarding/             # getting started, standards, contribution, quickref
└── api-reference/             # admin, adapter-ingest, operator APIs
```

Principle: numbered folders = reading order. Cross-refs dùng relative path. "Refined" docs nguồn từ `template-rebuild-docs/`; "NEW" docs author mới.

## Implementation Considerations & Risks

| Risk | Mitigation |
| --- | --- |
| Solo + multi-tenant SaaS tension | Portable design (Docker + env + interface), single-VPS MVP với migrate trigger rõ ràng. |
| RLS friction với SQLAlchemy async | Helper `with_tenant_context()`, app role không phải owner, Alembic raw SQL policies, set up 1 lần Phase 1. |
| LangGraph checkpointer bypass RLS | tenant_id trong checkpoint metadata + filter app-side; test cross-tenant denial. |
| Qdrant no RLS | App-layer mandatory tenant filter trong retrieval contract + isolation test là release gate. |
| Single VPS no HA | Nightly off-site backup (pg_dump + Qdrant snapshot → B2/Storage Box). |
| Langfuse + Clickhouse RAM (~2-4GB) | Nếu VPS chật, bắt đầu Langfuse Cloud free tier, self-host khi nâng cấp (ghi exit plan ADR-007). |
| chat_events phình (100 tenants × 10K/day) | Retention sweeper + Phase 7 monthly partitioning. |

## Success Metrics / Validation

- Tenant A không đọc được data/memory/vector/tool-config/audit của Tenant B (DB-level denial test).
- Adapter ingest p95 <= 500ms (excluding graph); support answer p95 <= 4s.
- Duplicate platform message idempotent.
- Disabled tool / missing credential fail closed + audit row.
- Operator replay 1 bad answer từ durable records (không phụ thuộc trace SaaS).
- Secret scan clean; prod rejects local KMS/dev secrets.

## Next Steps

1. Build `docs/` theo structure trên (this round).
2. ADR-001..009 ghi đầy đủ context/decision/consequences/alternatives.
3. Sau docs → `/ck:plan` cho Phase 0 (template hardening: migrate SQLModel→SQLAlchemy 2.0, Qdrant + Langfuse vào compose, KMSProvider skeleton).
4. Phase 1 (tenant control plane + RLS) là vertical slice đầu tiên.

## Dependencies

- D6 (secret manager) phụ thuộc D8 (deployment → chọn GCP KMS).
- D2 (RLS) + D4 (SQLAlchemy) phải xong Phase 0/1 trước mọi domain schema.
- D1 (Qdrant) + D3 (outbox) cần thêm services vào docker-compose Phase 0.
