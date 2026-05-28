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
- SQLAlchemy or SQLModel models.
- Alembic migrations.
- RLS middleware/session helper.
- CRUD for tenants, knowledge sources, plugins.
- Audit log for config changes.

Exit criteria:

- Tenant A cannot query tenant B rows in tests.
- API returns consistent error shapes.
- Migrations are repeatable from empty DB.

## Phase 2: Chat Ingress and Egress

Goal: adapters can send normalized events to the control plane and receive responses.

Deliverables:

- Telegram adapter first.
- Redis Streams ingress/egress.
- Internal message envelope schema.
- Consumer group processing.
- Idempotency by platform message id.

Exit criteria:

- Local Telegram sandbox can echo through the full bus.
- Duplicate events do not create duplicate responses.
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
- Citation-aware context builder.

Exit criteria:

- Tenant A vector queries cannot return tenant B chunks.
- Sync is idempotent.
- Failed source produces actionable sync error.

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
