# System Architecture

## Mục đích

Mô tả kiến trúc đích khi rebuild Agent Support trên template FastAPI + LangGraph, sau khi đã chốt 13 decisions. Nêu rõ phần template tái dùng, phần redesign, phần build mới.

## Đối tượng đọc

Engineering lead, backend engineer, AI engineer, DevOps, security reviewer, architect.

## Template Baseline

| Area | Available baseline |
| --- | --- |
| API | FastAPI app, API version prefix, auth routes, chat routes, health/metrics. |
| Agent runtime | LangGraph `StateGraph`, `AsyncPostgresSaver` checkpointer, chat/tool loop, streaming. |
| Memory | mem0 + pgvector per user, cache via Valkey/Redis hoặc in-memory fallback. |
| Auth | JWT user token + session token. |
| Persistence | SQLModel models, Alembic, PostgreSQL, pgvector. |
| LLM | OpenAI-backed service, retry, circular fallback, total timeout budget, structured output. |
| Tools | LangChain tools list (DuckDuckGo search, ask-human). |
| Observability | Langfuse callbacks, Prometheus, Grafana, structlog, request id. |
| Operations | Docker Compose, Makefile, CI/deploy, pre-commit, secret baseline. |
| Evaluation | Langfuse-trace-based eval runner, metric prompts, JSON reports. |

## Key Architecture Decision

**Không port runtime code cũ. Rebuild product behavior trên template primitives.** Template primitives hữu ích, nhưng product semantics phải redesign:

- Template user/session ≠ tenant/membership → thêm `tenant_memberships` + service principals (ADR-005).
- Template generic chat graph không đủ cho support/moderation/onboarding → domain graph.
- Template mem0 memory ≠ curated tenant knowledge RAG → source-backed pipeline riêng.
- Template DuckDuckGo search KHÔNG expose mặc định trong community support.
- **Template SQLModel → migrate SQLAlchemy 2.0 thuần** ở Phase 0 (ADR-004).
- **Vector backend → Qdrant** sau `VectorSearchProvider` (ADR-001).
- **Graph execution → async worker + Postgres outbox** (ADR-003), không sync trong request.

## Target Component View

```text
External platforms (Telegram per-tenant bot; Discord later)
  -> Telegram webhook /v1/webhook/telegram/{tenant_id}  (secret_token verify)
  -> Adapter (thin translator) -> Internal ingest API
  -> Adapter principal validate -> Tenant/platform resolver
  -> [TX] INSERT chat_events + processing_outbox -> 200 OK (<500ms)
  ----------------------------------------------------------------
  Agent runtime worker (polling SKIP LOCKED + LISTEN/NOTIFY)
  -> load trusted event -> LangGraph domain workflow (AsyncPostgresSaver)
  -> Capability/tool proxy
  -> VectorSearchProvider (Qdrant) — app-layer tenant filter
  -> policy_check -> INSERT delivery_outbox + agent_runs
  ----------------------------------------------------------------
  Delivery sender -> consume delivery_outbox -> platform send -> mark delivered

Admin/operator APIs (JWT user + service principals)
  -> Tenant config / Source management / Candidate review
  -> Plugin/capability policy / Audit & run inspection
```

## Runtime Topology (v1 — Single VPS, ADR-008)

| Service | Role |
| --- | --- |
| `api` | FastAPI: webhook ingest, admin/operator API. |
| `worker` | Outbox consumer: graph execution + delivery (same image, different command). |
| `postgres` | Source of truth: tenant/config/audit/runtime/outbox/source metadata. RLS enforced. |
| `qdrant` | Vector backend (external, app-layer tenant filter). |
| `redis` | Cache + rate limit only. **KHÔNG** dùng làm outbox. |
| `langfuse` | Self-host trace backend (+ Postgres + Clickhouse riêng). |
| `caddy`/`traefik` | Reverse proxy + Let's Encrypt. |

KMS: GCP Cloud KMS direct (free tier) sau `KMSProvider` interface. Service account JSON mount ngoài git.

> ⚠️ Security: webhook endpoints expose ra internet. Bắt buộc secret_token verify per Telegram bot + adapter principal scope check. Admin/operator API bắt buộc JWT auth + tenant role check.

## Target Data Flow: Support Message

```text
1. Telegram gửi update -> webhook /v1/webhook/telegram/{tenant_id}.
2. Verify secret_token; adapter normalize payload (no trusted tenant id in body).
3. API validate adapter principal -> resolve tenant/platform mapping.
4. [TX] INSERT chat_events (idempotency: tenant_id+platform+external_message_id)
        INSERT processing_outbox (event_id, status=pending, tenant_id)
   COMMIT -> return 200 OK (<500ms).
5. Worker SELECT ... FOR UPDATE SKIP LOCKED -> claim event.
6. Graph hydrate tenant config/policy/budget/allowed capabilities (SET LOCAL tenant).
7. classify_intent -> risk_screen -> route.
8. support_rag_flow: rag.search qua capability proxy.
9. VectorSearchProvider (Qdrant) enforce tenant/source/visibility/active filter (app-layer).
10. LLM draft answer từ bounded context.
11. policy_check + citation check -> send / refuse / clarify / escalate.
12. INSERT delivery_outbox + agent_runs/steps.
13. Delivery sender consume -> Telegram send -> delivery_receipt.
14. agent_run, steps, tool_calls, audit có sẵn cho review.
```

Chi tiết sequence diagrams: [data-flow-diagrams.md](data-flow-diagrams.md).

## Target LangGraph Shape

Template graph hiện là two-node loop. Product graph:

```text
hydrate_context
-> classify_intent
-> risk_screen
-> route
   -> support_rag_flow
   -> moderation_shadow_flow
   -> onboarding_flow
   -> ops_harness_gate
   -> safe_fallback
-> policy_check
-> response_builder
-> emit_outbound
-> record_run
```

Graph serializable + testable. Mỗi node return explicit state update. Không node nào bypass tenant policy, tool proxy, retrieval provider. Chi tiết: [core-agent-design.md](core-agent-design.md).

## Template Mapping

| Product need | Template area extend | Notes |
| --- | --- | --- |
| Tenant-aware auth | JWT auth + DB service | Thêm membership, roles, service principals. |
| Support endpoint | Chat route + LangGraph | Replace generic graph với domain graph. |
| Agent run replay | Checkpointer + new run tables | Checkpointer = runtime state; audit tables = product evidence. |
| Tool permissioning | LangGraph tools package | Tool proxy + capability registry trước khi expose. |
| RAG knowledge | New provider | Curated source-backed RAG tách khỏi generic memory; Qdrant backend. |
| Observability | Langfuse, metrics, structlog | Thêm tenant/run/tool labels + redaction. |
| Eval | eval framework | Thêm product-specific metrics/datasets. |
| Persistence | SQLModel → SQLAlchemy 2.0 | Migrate Phase 0; Alembic raw SQL cho RLS. |

## Features To Build From Scratch

- Tenant entity + membership model.
- Adapter credential + platform mapping (per-tenant Telegram bot).
- Internal ingest contract.
- Durable chat_events + processing/delivery outbox.
- Agent run + run step tables.
- Moderation decisions/actions + review queue.
- Knowledge source/version/document/chunk/sync job/candidate model.
- Source-backed RAG contract (`VectorSearchProvider` → Qdrant).
- Capability manifest registry + tool proxy.
- Tenant-scoped credential handles (KMS envelope).
- Tenant-aware audit log.
- Incident trace/run viewer APIs.

## Features To Drop Or Defer

- Generic autonomous multi-agent default path.
- Public plugin marketplace.
- Runtime-loaded tenant skills.
- Broad web search trong normal support.
- Automated destructive moderation trước review gates.
- Direct vector DB access từ arbitrary graph nodes.

## Architecture Guardrails

- Route handlers thin: auth/context, validation, service/graph call, response.
- Tenant-owned data access qua repositories/services với tenant context (SET LOCAL).
- Graph nodes gọi service/tool interface, không raw DB/vector client.
- Adapters translate platform payloads; không own business policy.
- Tool proxy own capability permission, không phải model.
- Observability exporters downstream của redaction.

## Resolved Decisions (đã đóng)

Open questions của bản draft cũ đã resolve: graph execution = worker/outbox (ADR-003); vector = Qdrant (ADR-001); isolation = RLS (ADR-002); ORM = SQLAlchemy 2.0 (ADR-004); deployment = single VPS + GCP KMS (ADR-008); trace = Langfuse self-host (ADR-007).

## References

- [Domain And Tenant Model](domain-and-tenant-model.md)
- [Core Agent Design](core-agent-design.md)
- [Adapters And Integrations](adapters-and-integrations.md)
- [Data Flow Diagrams](data-flow-diagrams.md)
- [Persistence Strategy](../02-persistence/persistence-strategy.md)
- [ADR index](../06-decisions/)
