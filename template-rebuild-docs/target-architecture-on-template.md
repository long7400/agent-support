# Target Architecture On The FastAPI LangGraph Template

## Mục đích

Tài liệu này mô tả kiến trúc đích khi xây Agent Support trên template FastAPI + LangGraph, nêu rõ phần template đã có, phần cần giữ từ product/domain, phần phải thiết kế lại, và phần nên bỏ.

## Đối tượng đọc

Engineering lead, backend engineer, AI engineer, DevOps, security reviewer, và architect.

## Template Baseline

Template hiện có:

| Area | Available baseline |
| --- | --- |
| API | FastAPI app, API version prefix, auth routes, chat routes, health/metrics. |
| Agent runtime | LangGraph `StateGraph`, checkpointer via PostgreSQL saver, chat/tool loop, streaming. |
| Memory | mem0 + pgvector per user, cache via Valkey/Redis or in-memory fallback. |
| Auth | JWT user token and session token. |
| Persistence | SQLModel models, Alembic migrations, PostgreSQL, pgvector. |
| LLM | OpenAI-backed service with retry, circular fallback, total timeout budget, structured output. |
| Tools | LangChain tools list with DuckDuckGo search and ask-human. |
| Observability | Langfuse callbacks, Prometheus metrics, Grafana dashboards, structlog, request id. |
| Operations | Docker Compose, Makefile commands, CI/deploy workflows, pre-commit, secret baseline. |
| Evaluation | Langfuse-trace-based eval runner with metric prompts and JSON reports. |

## Key Architecture Decision

Do not port prior runtime code. Rebuild product behavior on top of template primitives.

Template primitives are useful, but product semantics must be redesigned:

- Template user/session is not tenant/membership.
- Template generic chat graph is not enough for support/moderation/onboarding.
- Template mem0 memory is not curated tenant knowledge RAG.
- Template DuckDuckGo search should not be exposed by default in community support.
- Template SQLModel is already present, so use it pragmatically unless the team decides to replace it before schema work.

## Target Component View

```text
External platforms
  -> Telegram adapter / Discord adapter
  -> Internal ingest API
  -> Tenant/platform resolver
  -> Durable chat event + delivery outbox
  -> Agent runtime worker or async graph execution
  -> LangGraph domain workflow
  -> Capability/tool proxy
  -> Knowledge retrieval provider
  -> Outbound delivery envelope
  -> Platform send

Admin/operator APIs
  -> Tenant config
  -> Source management
  -> Candidate review
  -> Plugin/capability policy
  -> Audit and run inspection
```

## Recommended Template Mapping

| Product need | Template area to extend | Notes |
| --- | --- | --- |
| Tenant-aware auth | JWT auth and database service | Add tenant membership, roles, service principals. |
| Chat/support endpoint | Chat route and LangGraph agent | Replace generic graph with domain graph. |
| Agent run replay | LangGraph checkpointer + new run tables | Checkpointer is runtime state; audit tables are product evidence. |
| Tool permissioning | LangGraph tools package | Add tool proxy and capability registry before exposing tools. |
| RAG knowledge | mem0/pgvector patterns or new provider | Curated source-backed RAG must be separate from generic memory. |
| Observability | Langfuse, metrics, structlog | Add tenant/run/tool labels and redaction policy. |
| Eval | eval framework | Add product-specific metrics and datasets. |
| Docker | Compose stack | Add adapters, workers, Redis/Valkey mode, optional vector backend. |

## Target Data Flow: Support Message

```text
1. Platform adapter receives message.
2. Adapter normalizes platform payload and sends it with adapter credential.
3. API validates adapter credential and resolves tenant/platform mapping.
4. API persists chat event and idempotency record.
5. Runtime graph hydrates tenant config, policy, model budget, and allowed capabilities.
6. Graph classifies intent and screens risk.
7. Support path calls `rag.search` through tool/capability boundary.
8. Retrieval provider enforces tenant/source/visibility/active filters.
9. LLM drafts answer from bounded context.
10. Policy/citation check decides send, refuse, clarify, or escalate.
11. Outbound delivery record/envelope is created.
12. Adapter sends platform message and records delivery result.
13. Agent run, steps, tool calls, and audit summaries are available for review.
```

## Target LangGraph Shape

Template graph is currently a two-node loop. Product graph should evolve to:

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

The graph should stay serializable and testable. Each node returns explicit state updates. No node should bypass tenant policy, tool proxy, or retrieval provider.

## Template Features To Keep

- FastAPI app/middleware pattern.
- JWT/auth utilities as starting point.
- Alembic migration ownership.
- PostgreSQL checkpointer pattern for LangGraph.
- LLM service retry/fallback/timeout concept.
- Structured logging style.
- Prometheus/Grafana metrics surface.
- Langfuse callback integration after redaction policy.
- Evaluation framework structure.
- Docker and Makefile ergonomics.

## Template Features To Redesign

| Existing template feature | Redesign for Agent Support |
| --- | --- |
| User/session auth | Add tenant membership, roles, adapter principals, service identities. |
| Generic chat graph | Replace with support/moderation/onboarding workflow. |
| mem0 per-user memory | Restrict or disable until memory governance is accepted; build source-backed knowledge retrieval separately. |
| DuckDuckGo tool | Disable by default for tenant support; expose only as tenant-enabled capability. |
| Direct tool list binding | Tool proxy filters allowed capabilities per tenant/run. |
| SQLModel-only domain model | Accept for template-native rebuild but keep DTO/domain boundaries clean and use Alembic raw SQL for RLS/policies. |
| Generic eval metrics | Add product evals: source grounding, tenant leakage, moderation safety, tool denial, stale-source refusal. |

## Features To Build From Scratch

- Tenant entity and membership model.
- Adapter credential and platform mapping.
- Internal ingest contract for Telegram/Discord.
- Durable chat event and outbound delivery/outbox model.
- Agent run and run step tables.
- Moderation decisions/actions and review queue.
- Knowledge source/version/document/chunk/sync job/candidate model.
- Source-backed RAG contract.
- Capability manifest registry.
- Tool proxy with policy/audit.
- Tenant-scoped credential handles.
- Tenant-aware audit log.
- Incident trace/run viewer APIs.

## Features To Drop Or Defer

- Any assumption that path/module names from a non-template repo exist.
- Generic autonomous multi-agent default path.
- Public plugin marketplace.
- Runtime-loaded tenant skills.
- Broad web search in normal support.
- Automated destructive moderation until review gates exist.
- Direct vector DB access from arbitrary graph nodes.
- Deep Agents harness as the default for every message.

## Persistence Strategy

Template uses PostgreSQL and pgvector. Recommended sequence:

1. Use PostgreSQL for tenant/config/audit/runtime metadata.
2. Use Alembic for all app schema and RLS/equivalent isolation SQL.
3. Define `VectorSearchProvider` before choosing final vector backend.
4. Start with template-native pgvector only if it can pass tenant/source/visibility/isolation tests.
5. Add Qdrant later if scale, operational separation, or vector filtering requirements justify it.
6. Keep source metadata and activation in PostgreSQL regardless of vector backend.

## Runtime Deployment Shape

Initial services:

- FastAPI API.
- PostgreSQL with pgvector.
- Valkey/Redis for cache/rate limit and optionally queues.
- Langfuse optional.
- Prometheus/Grafana optional.

Product services to add:

- Telegram adapter.
- Agent runtime worker if graph work leaves HTTP request path.
- Delivery/reclaim worker for outbound reliability.
- Knowledge sync worker.
- Optional Discord adapter.
- Optional MCP/tool services.
- Optional Qdrant if adopted.

## Architecture Guardrails

- Route handlers should stay thin: auth/context, validation, service/graph call, response.
- Tenant-owned data access must go through repositories/services with tenant context.
- Graph nodes call service/tool interfaces, not raw DB/vector clients.
- Adapters translate platform payloads; they do not own business policy.
- Tool proxy owns capability permission, not the model.
- Observability exporters are downstream of redaction.

## Open Decisions

- Should graph execution remain in request path for MVP, or move to a worker after ingest?
- Should v1 knowledge retrieval use pgvector or Qdrant behind provider contract?
- Which RLS/equivalent isolation model is easiest to implement safely with SQLModel?
- Which production deployment target is preferred: single Compose/GCP Cloud Run/GKE/other?
- Which observability sink is allowed for production tenant traces?
