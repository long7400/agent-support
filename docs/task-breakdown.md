# Task Breakdown

## Milestone 0: Foundation

| ID | Task | Acceptance |
| --- | --- | --- |
| M0-001 | Create monorepo directories. | Expected top-level folders exist and are documented. |
| M0-002 | Add local Docker Compose. | Postgres, Redis, Qdrant boot locally. |
| M0-003 | Add Python service scaffold. | `core/api` starts and returns `/healthz`. |
| M0-004 | Add CI. | Lint, type, test, secret scan run on push. |
| M0-005 | Add config loading. | Environment config validates required values. |
| M0-006 | Add agent instructions. | `AGENTS.md` points agents to docs, validation, and architecture boundaries. |

## Milestone 1: Tenancy

| ID | Task | Acceptance |
| --- | --- | --- |
| M1-001 | Model `tenants`. | Migration creates table with status and model config. |
| M1-002 | Model `tenant_plugins`. | Plugins can be enabled/disabled per tenant. |
| M1-003 | Implement RLS session helper. | Tests prove RLS blocks cross-tenant reads. |
| M1-004 | Add audit log. | Config mutations create audit rows. |
| M1-005 | Add admin API auth placeholder. | Unauthorized requests are rejected. |
| M1-006 | Add repository layer conventions. | SQLAlchemy repositories keep DB access out of routes and domain logic. |

## Milestone 2: Messaging

| ID | Task | Acceptance |
| --- | --- | --- |
| M2-001 | Define message envelope schema. | Schema validates Telegram and Discord events. |
| M2-002 | Implement Redis ingress consumer. | Consumer reads and acknowledges message. |
| M2-003 | Implement egress publisher. | Adapter can read response event. |
| M2-004 | Implement Telegram adapter. | Sandbox message reaches API. |
| M2-005 | Add idempotency. | Duplicate platform message is ignored. |

## Milestone 3: Agent Runtime

| ID | Task | Acceptance |
| --- | --- | --- |
| M3-001 | Define `AgentState`. | Type checks pass; state is serializable. |
| M3-002 | Add graph nodes. | Classify, moderate, retrieve, draft, policy, emit nodes exist. |
| M3-003 | Add checkpoint persistence. | Run can resume/replay with same trace id. |
| M3-004 | Add mock LLM tests. | Graph unit tests do not call real LLM. |
| M3-005 | Add run tracing. | Node latency and final status are stored. |

## Milestone 4: RAG

| ID | Task | Acceptance |
| --- | --- | --- |
| M4-001 | Model knowledge sources. | Source config and status stored per tenant. |
| M4-002 | Build sync job lifecycle. | Pending, running, succeeded, failed states work. |
| M4-003 | Build index worker. | Source chunks upsert into Qdrant with tenant payload. |
| M4-004 | Build query service. | Query filters by tenant and returns citations. |
| M4-005 | Add isolation tests. | Cross-tenant vector leakage test fails closed. |
| M4-006 | Add vector provider interface. | Qdrant provider satisfies shared query contract. |
| M4-007 | Add TurboVec spike provider. | Provider is feature-flagged and disabled by default. |
| M4-008 | Add RAG benchmark fixtures. | Qdrant and TurboVec run against same corpus and queries. |
| M4-009 | Add TurboVec rebuild/fallback tests. | Local index can rebuild and failures fall back or fail closed. |

## Milestone 5: Tools

| ID | Task | Acceptance |
| --- | --- | --- |
| M5-001 | Define MCP registry. | Enabled tools are loaded from DB. |
| M5-002 | Add tool permission check. | Disabled tools cannot execute. |
| M5-003 | Implement `rag.search`. | Tool returns bounded context with citations. |
| M5-004 | Implement `crypto.price`. | Tool uses configured provider and timeout. |
| M5-005 | Add tool audit log. | Every tool call stores status and summary. |

## Milestone 6: Moderation

| ID | Task | Acceptance |
| --- | --- | --- |
| M6-001 | Define policy matrix. | Tenant can configure action per category. |
| M6-002 | Add shadow mode. | Decisions are logged without action. |
| M6-003 | Add enforcement executor. | Delete/warn/ban actions are audited. |
| M6-004 | Add review queue. | Low-confidence cases can be reviewed. |
| M6-005 | Add regression set. | Known scam/toxic examples are tested. |

## Milestone 7: Operations

| ID | Task | Acceptance |
| --- | --- | --- |
| M7-001 | Add trace viewer API. | Operator can fetch run by trace id. |
| M7-002 | Add sync retry API. | Failed sync can be retried safely. |
| M7-003 | Add metrics. | Latency, errors, token usage, and tool failures are exported. |
| M7-004 | Add deployment docs. | Local, staging, production steps are documented. |
| M7-005 | Add backup/restore drill. | Restore procedure is tested in staging. |
