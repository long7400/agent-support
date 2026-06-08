# Domain And Tenant Model

## Mục đích

Định nghĩa domain entities, tenant ownership, authorization context, data boundaries, isolation invariants cho Agent Support.

## Đối tượng đọc

Backend engineer, database engineer, AI engineer, security reviewer, QA, operator.

## Core Domain Terms

Xem [glossary.md](../00-foundation/glossary.md) cho danh sách đầy đủ. Term quan trọng: Tenant, Platform, Tenant platform, Chat event, Trusted event, Agent run, Knowledge source, Source version, Knowledge chunk, Capability, Tool call, Moderation action, Audit event.

## Tenant Boundary

Tenant boundary là invariant quan trọng nhất:

- Tenant id KHÔNG lấy từ untrusted request body.
- Tenant id đến từ JWT/session, adapter principal, platform mapping, hoặc operator context đã xác thực.
- Graph state nhận trusted tenant id sau hydration và không mutate.
- Mọi tenant-owned row có `tenant_id`.
- Mọi vector/memory/tool/config read lọc tenant.
- Logs/traces có tenant id nhưng không chứa secrets/full private payload.

Enforce ở DB layer: **PostgreSQL RLS** (ADR-002) với `SET LOCAL app.current_tenant` per-transaction. Qdrant không có RLS → app-layer mandatory filter.

## Tenant Lifecycle

| Status | Runtime behavior |
| --- | --- |
| `active` | Cho phép ingest, graph, retrieval, tool calls theo policy. |
| `disabled` | Từ chối graph/tool/outbound; admin vẫn xem audit/config. |
| `suspended` | Từ chối runtime, hạn chế admin mutation tùy policy. |
| `deleting` | Dừng ingest mới, drain jobs, tombstone/deletion workflow (GDPR <30d, ADR retention). |

Tenant status reload ở worker/graph boundary, không chỉ check lúc ingest.

## Actors And Principals

| Principal | Trust boundary | Allowed actions |
| --- | --- | --- |
| User | JWT user/session | Chat/session endpoints; không đủ cho tenant admin nếu chưa mapped role. |
| Tenant admin | `tenant_memberships` role | Configure source, policy, adapter, tools cho own tenant. |
| Tenant moderator | `tenant_memberships` role | Review candidates, moderation proposals, false positives. |
| Platform operator | Internal admin (có role `BYPASSRLS` riêng) | Manage tenants, inspect audit, incident workflows. |
| Adapter principal | Platform integration credential | Submit normalized events cho scoped platform/workspace/channel. |
| Worker principal | Internal service identity | Consume outbox, run graph, sync sources, execute allowed tools. |
| Tool principal | Capability-scoped identity | Execute một tool dưới tenant/capability policy. |
| Service principal | API key (automation/CI) | Programmatic admin theo scope (ADR-005). |

Auth model chi tiết: [authn-authz.md](../03-security/authn-authz.md) (ADR-005).

## Recommended Domain Entities

> Schema DDL đầy đủ: [schema-reference.md](../02-persistence/schema-reference.md).

### Tenant And Membership
```text
tenants
tenant_memberships
tenant_roles
service_principals
tenant_config_versions
```
- Tenant config có version. Membership grant role per tenant. Operator/admin actions có audit. Production auth không phụ thuộc 1 static admin token.

### Platform Mapping
```text
tenant_platforms          # per-tenant Telegram bot mapping
adapter_credentials       # credential handle (KMS envelope) + scope
platform_channels
```
- One active platform identity → đúng một tenant. Adapter credential scope theo platform/workspace/chat/channel. Raw bot token KHÔNG ở config JSON — lưu qua KMS handle (ADR-006).

### Messaging
```text
chat_events
processing_outbox         # graph work (ADR-003)
delivery_outbox           # outbound send (ADR-003)
delivery_receipts
```
- Inbound idempotency: UNIQUE `(tenant_id, platform, external_message_id)`. Outbound link tới inbound event + agent run. Outbox = durable transport, exactly-once via same-DB transaction.

### Agent Runtime
```text
agent_runs
agent_run_steps
graph_checkpoint_metadata  # tenant_id trong checkpoint metadata (RLS-aware, ADR-002)
model_calls
```
- Run tied tới trusted event + tenant. Step có node name, status, latency, redacted summary. Model calls có provider/model/version/cost/token. Checkpoints support resume/replay; audit tables = product evidence.

### Knowledge
```text
knowledge_sources
knowledge_source_versions
knowledge_documents
knowledge_chunks           # metadata; vector payload ở Qdrant
knowledge_sync_jobs
knowledge_candidates
knowledge_ingest_audit
```
- Source version activation chặn partial sync visibility. Chunk có citation metadata. Candidate cần review. Deleted/tombstoned source không retrievable.

### Capabilities
```text
plugin_manifests
plugin_capabilities
tenant_capability_enablement
tenant_tool_policies
tenant_credential_handles   # KMS envelope (ADR-006)
tool_calls
sub_agent_invocations
```
- Capability execution re-check enablement ngay trước call. Tool policy capture risk, timeout, budget, approval, rate limit. Credential handle scope theo tenant + capability.

### Moderation
```text
moderation_decisions
moderation_actions
review_queue_items
policy_versions
```
- Shadow/propose/enforce versioned. Destructive action record policy, confidence, reviewer/approval, platform response, idempotency key.

## Data Ownership Matrix

| Data | Owner | Tenant scoped? | Prompt access |
| --- | --- | --- | --- |
| Tenant config | Control plane | Yes | Hydrated summary/version. |
| Platform message | Messaging service | Yes | Bounded recent context only. |
| Agent run state | Agent runtime | Yes | Current graph state only. |
| Knowledge source/chunk | Knowledge service | Yes | Through RAG retrieval only. |
| Tool config | Capability registry | Yes | Filtered allowed specs only. |
| Credential material | Secret subsystem (KMS) | Yes | Never. |
| Audit record | Audit subsystem | Yes/operator-owned | Not prompt context by default. |
| Eval fixture | Eval subsystem | Usually yes | Offline after redaction. |

## Trusted Context Contract

Mọi runtime operation mang:

```json
{
  "trace_id": "uuid",
  "tenant_id": "uuid",
  "actor_type": "user|tenant_admin|moderator|operator|adapter|worker|tool",
  "actor_id": "stable-redacted-id",
  "platform": "telegram|discord|null",
  "channel_id": "string|null",
  "thread_id": "string|null",
  "run_id": "uuid|null"
}
```

Rules:
- `tenant_id` immutable sau khi context tạo.
- `trace_id` generate ở ingress nếu absent.
- Internal services nhận typed context, không phải arbitrary tenant id string.
- Public DTO không cho client override trusted context fields.

## Memory Taxonomy

Không dùng một generic memory bucket.

| Memory type | Storage | Prompt access | Notes |
| --- | --- | --- | --- |
| Runtime state | LangGraph checkpointer + run records | Direct while bounded | Current graph only. |
| Recent conversation | chat_events + summaries | Bounded summary/direct | Tenant-scoped, retention controlled. |
| Tenant config/policy | PostgreSQL | Hydrated summary | Versioned, audited. |
| Knowledge memory | Qdrant (behind provider) | Retrieved with citations | Approved sources only. |
| Workflow state | PostgreSQL | Service-shaped summary | Not scratch files. |
| Member profile | PostgreSQL (later) | Restricted summary | Needs privacy policy. |
| Tool/plugin memory | Manifest/config tables | Allowed specs only | No raw secrets. |
| Audit/replay | PostgreSQL + traces | Not prompt by default | Incident evidence. |
| Secret handles | KMS + Postgres credential table | Never | Resolve after permission check. |

## Isolation Invariants

- User từ Tenant A không list/query/retrieve/infer được Tenant B data.
- Tenant-disabled runtime không dùng stale cached permissions.
- Tool không execute với credential handle không scope cho current tenant/capability.
- Vector query thiếu tenant filter = bug, không phải optimization.
- Model output không tạo trusted tenant context/policy/credential/profile memory trực tiếp.
- Trace export không phải compliance audit record.

## Resolved Design Decisions

Open question cũ đã chốt:
- Tenant admin auth → JWT user + service principals + memberships (ADR-005).
- Knowledge RAG → Qdrant ngay v1 sau provider contract (ADR-001).
- Retention → 90d chat / 180d runs / 2y audit + per-tenant override + GDPR <30d (xem [persistence-strategy.md](../02-persistence/persistence-strategy.md)).
- Tenant deletion propagation → hard delete SQL + Qdrant collection + Langfuse project + KMS DEK revoke (xem persistence + runbooks).

## References

- [System Architecture](system-architecture.md)
- [Schema Reference](../02-persistence/schema-reference.md)
- [Authn/Authz](../03-security/authn-authz.md)
- [ADR-002 Tenant Isolation](../06-decisions/adr-002-tenant-isolation-model.md)
