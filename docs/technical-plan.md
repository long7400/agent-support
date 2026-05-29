# Technical Plan

## Strategy

Build the platform in vertical slices. Each slice must prove a runtime boundary, tenant isolation, and observability before adding more agent capability.

## Phase 0: Repository Foundation

Goal: create a production-shaped monorepo before feature work.

Deliverables:

- `core/` Python service scaffold.
- `adapters/telegram-bot/` and `adapters/discord-bot/` placeholders.
- `mcp_servers/` tool boundary scaffold.
- `infra/docker-compose.yml` for Postgres, Redis, Qdrant.
- `docs/` accepted as source of truth.
- CI for lint, tests, type checks, and secret scan.

Exit criteria:

- Fresh clone can run local infra.
- Health endpoint works.
- CI passes.

## Phase 1: Tenant Control Plane

Goal: tenant config, platform connections, plugin config, and RLS-backed metadata.

Deliverables:

- FastAPI app.
- SQLAlchemy 2.x models.
- Pydantic request/response/config schemas kept separate from ORM models.
- Alembic migrations.
- RLS session helper.
- Admin auth placeholder, trace id, and consistent API error envelope.
- CRUD for tenants and tenant plugins.
- Audit log for config changes.

Deferred from this phase:

- `tenant_platforms` and chat adapter connection runtime.
- Knowledge source CRUD and Qdrant/RAG provisioning.
- OAuth/OIDC/JWT admin users.

Exit criteria:

- Tenant A cannot query tenant B rows in tests.
- API returns consistent error shapes.
- Migrations are repeatable from empty DB.
- Config mutations create audit rows.

## Phase 2: Chat Ingress and Egress

Goal: adapters can send normalized events to the control plane and receive responses.

Phase 2A messaging backbone deliverables now implemented locally:

- Internal normalized message envelope schema.
- Tenant platform mapping table for Telegram/Discord workspace/channel identity.
- PostgreSQL-backed `chat_events` idempotency by platform message id.
- Tenant-owned `stream_outbox` retry state for Redis publish attempts.
- Redis Streams ingress/outbound helpers with bounded `XADD MAXLEN ~`.
- Backpressure checks for memory, stream length, and pending entries.
- Internal `/internal/messages/ingest` API.
- Deterministic `agent-support-worker-stub` local loop with active-tenant
  verification before processing.

Deferred to Phase 2B:

- Real Telegram adapter runtime and sandbox bot.
- Discord adapter runtime.
- DLQ/reclaim workflow for repeatedly pending messages.
- Production auth model for adapter-to-control-plane traffic.

Deferred beyond Phase 2:

- LangGraph, RAG, MCP, and full agent response generation.
- Celery for chat ingress/egress. Redis Streams remain the chat transport; Celery
  may be reconsidered later for coarse background jobs.

Exit criteria:

- Local normalized event can echo through DB, Redis ingress, worker stub, and
  Redis outbound.
- Duplicate events do not create duplicate responses.
- Disabled tenants are rejected before worker publish/ACK.
- Trace id ties adapter logs to API logs.

## Phase 3: Agent Engine

Goal: deterministic LangGraph workflow for support and moderation.

Deliverables:

- Agent state schema.
- Core graph nodes.
- Tenant persona loading.
- Policy check node.
- Checkpointing/replay for agent runs.

Exit criteria:

- A saved event can be replayed deterministically with mocked LLM/tool calls.
- Every node has unit tests.
- Agent run stores latency, status, and output summary.

## Phase 4: Knowledge Sync and RAG

Goal: tenant docs can be indexed and queried safely.

Deliverables:

- Knowledge source model.
- Sync job lifecycle.
- CocoIndex or fallback indexing worker adapter.
- Qdrant collection and payload indexes.
- LlamaIndex Qdrant query service.
- `VectorSearchProvider` interface with Qdrant as the first implementation.
- TurboVec accelerator spike behind feature flag after Qdrant baseline passes.
- Citation-aware context builder.

Exit criteria:

- Tenant A vector queries cannot return tenant B chunks.
- Sync is idempotent.
- Failed source produces actionable sync error.
- TurboVec is not enabled by default and can be disabled without data migration.

### Phase 4A: TurboVec Accelerator Spike

Goal: decide whether TurboVec should become an accepted read-path accelerator.

Deliverables:

- `TurboVecVectorSearchProvider` using `turbovec[llama-index]`.
- Fixture corpus shared with Qdrant provider tests.
- Benchmark script for recall, p95 latency, memory, build time, and persist/load time.
- Rebuild flow from Qdrant/source chunk data.
- Feature flag: `RAG_ACCELERATOR=none|turbovec`.

Exit criteria:

- ADR 0002 gates pass, or TurboVec stays disabled.
- Tenant/source filtering behaves the same as Qdrant baseline.
- TurboVec failure falls back to Qdrant or fails closed.
- Metrics expose accelerator hit rate, build time, load time, errors, and fallback count.

## Phase 5: MCP Tools and Plugin Runtime

Goal: enabled tenant tools are dynamically bound and permissioned.

Deliverables:

- MCP client registry.
- Tool allowlist per tenant.
- Tool timeout, retry, and audit log.
- Built-in tools: `rag.search`, `crypto.price`, `web.search`.

Exit criteria:

- Disabled tool cannot be invoked even if model requests it.
- Tool inputs and outputs are schema-validated.
- Tool credentials never appear in logs.

## Phase 6: Moderation Enforcement

Goal: scam/toxic detection can run in shadow mode and enforcement mode.

Deliverables:

- Moderation classifier node.
- Tenant policy matrix.
- Action executor for delete/warn/ban.
- Review queue for uncertain cases.

Exit criteria:

- Shadow mode records decisions without action.
- Enforcement mode respects tenant policy.
- False positive review can override policy.

## Phase 7: Admin Dashboard and Operations

Goal: operators can configure tenants and inspect agent behavior.

Deliverables:

- Dashboard or admin API console.
- Trace viewer.
- Sync status and retry controls.
- Plugin toggles.
- Cost/latency dashboards.

Exit criteria:

- Admin can configure a tenant without database access.
- Operator can debug one bad answer from trace to source chunks.

## Phase 8: Production Hardening

Goal: release readiness.

Deliverables:

- Load test.
- Tenant isolation test suite.
- Security review.
- Deployment manifests.
- Backups and restore drill.
- Incident runbook.

Exit criteria:

- Validation checklist passes.
- Rollback path is documented and tested.
- Production secrets are managed outside git.
