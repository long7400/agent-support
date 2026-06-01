# Domain And Tenant Model

## Mục đích

Tài liệu này định nghĩa domain entities, tenant ownership, authorization context, data boundaries, và isolation invariants cho Agent Support.

## Đối tượng đọc

Backend engineer, database engineer, AI engineer, security reviewer, QA, và operator.

## Core Domain Terms

| Term | Meaning |
| --- | --- |
| Tenant | Một crypto project/customer sử dụng platform. |
| Platform | Telegram hoặc Discord. |
| Tenant platform | Mapping giữa tenant và workspace/channel/guild/chat external. |
| Chat event | Inbound/outbound message event đã chuẩn hóa và gắn tenant. |
| Agent run | Một lần graph xử lý một trusted inbound event. |
| Knowledge source | Nguồn official hoặc approved dùng cho RAG. |
| Source version | Snapshot bất biến của một source ở thời điểm sync. |
| Knowledge chunk | Đơn vị text đã chunk/embed và có citation metadata. |
| Capability | Tool, sub-agent, prompt pack, policy pack, hoặc MCP reference có manifest. |
| Tool call | Một attempt gọi capability có input/output/status/audit. |
| Moderation action | Shadow/proposal/enforcement record cho risk decision. |
| Audit event | Bản ghi durable về mutation hoặc capability/action attempt. |

## Tenant Boundary

Tenant boundary là invariant quan trọng nhất:

- Tenant id không được lấy từ untrusted request body.
- Tenant id phải đến từ JWT/session, adapter principal, platform mapping, hoặc operator context đã xác thực.
- Graph state nhận trusted tenant id sau hydration và không được mutate.
- Mọi tenant-owned row có tenant id hoặc equivalent ownership key.
- Mọi vector/memory/tool/config read phải lọc tenant.
- Logs/traces có tenant id nhưng không chứa secrets hoặc full private payload.

## Tenant Lifecycle

| Status | Runtime behavior |
| --- | --- |
| `active` | Cho phép ingest, graph, retrieval, tool calls theo policy. |
| `disabled` | Từ chối graph/tool/outbound; admin vẫn xem được audit/config. |
| `suspended` | Từ chối runtime và hạn chế admin mutation tùy policy. |
| `deleting` | Dừng ingest mới, drain jobs, tombstone/deletion workflow. |

Tenant status phải được reload ở worker/graph boundary, không chỉ kiểm tra lúc ingest.

## Actors And Principals

| Principal | Trust boundary | Allowed actions |
| --- | --- | --- |
| User | Template JWT user/session | Chat/session endpoints; không đủ cho tenant admin nếu chưa mapped role. |
| Tenant admin | Future tenant role | Configure source, policy, adapter, tools for own tenant. |
| Platform operator | Internal admin | Manage tenants, inspect audit, run incident workflows. |
| Adapter principal | Platform integration credential | Submit normalized events for scoped platform/workspace/channel. |
| Worker principal | Internal service identity | Consume queues, run graph, sync sources, execute allowed tools. |
| Tool principal | Capability-scoped identity | Execute one tool under tenant/capability policy. |

Template hiện có JWT user/session. Rebuild cần thêm tenant membership/role model thay vì giả định user == tenant.

## Recommended Domain Entities

### Tenant And Membership

```text
tenants
tenant_memberships
tenant_roles
tenant_api_keys or service_principals
```

Required behavior:

- Tenant config has version.
- Membership grants role per tenant.
- Operator/admin actions have audit.
- Production auth does not rely on one static admin token.

### Platform Mapping

```text
tenant_platforms
adapter_credentials
platform_channels
```

Required behavior:

- One active platform identity resolves to exactly one tenant unless an explicit routing policy says otherwise.
- Adapter credential is scoped by platform, workspace/guild/chat, and optional channel.
- Raw bot tokens live outside normal config JSON.

### Messaging

```text
chat_events
stream_outbox or delivery_outbox
delivery_receipts
```

Required behavior:

- Inbound event idempotency by tenant/platform/channel/platform message id/direction.
- Outbound records link to inbound event and agent run.
- Queue transport can retry safely without duplicate side effects.

### Agent Runtime

```text
agent_runs
agent_run_steps
graph_checkpoints
model_calls
```

Required behavior:

- Agent run is tied to trusted event and tenant.
- Step records include node name, status, latency, redacted summary.
- Model calls include provider/model/version/cost/token usage when available.
- Checkpoints support replay/resume but audit tables remain the product evidence.

### Knowledge

```text
knowledge_sources
knowledge_source_versions
knowledge_documents
knowledge_chunks
knowledge_sync_jobs
knowledge_candidates
knowledge_ingest_audit
```

Required behavior:

- Source version activation prevents partial sync visibility.
- Chunks have citation metadata.
- Candidate knowledge requires review before RAG.
- Deleted or tombstoned sources are not retrieved.

### Capabilities

```text
plugin_manifests
plugin_capabilities
tenant_capability_enablement
tenant_tool_policies
tenant_credential_handles
tool_calls
sub_agent_invocations
```

Required behavior:

- Capability execution re-checks enablement immediately before call.
- Tool policies capture risk, timeout, budget, approval, rate limit.
- Credential handles are scoped to tenant and capability.

### Moderation

```text
moderation_decisions
moderation_actions
review_queue_items
policy_versions
```

Required behavior:

- Shadow/propose/enforce modes are versioned.
- Destructive action records policy, confidence, reviewer/approval if any, platform response, and idempotency key.

## Data Ownership Matrix

| Data | Owner | Tenant scoped? | Prompt access |
| --- | --- | --- | --- |
| Tenant config | Control plane | Yes | Hydrated summary/version. |
| Platform message | Messaging service | Yes | Bounded recent context only. |
| Agent run state | Agent runtime | Yes | Current graph state only. |
| Knowledge source/chunk | Knowledge service | Yes | Through RAG retrieval only. |
| Tool config | Capability registry | Yes | Filtered allowed specs only. |
| Credential material | Secret subsystem | Yes | Never. |
| Audit record | Audit subsystem | Yes or operator-owned | Not prompt context by default. |
| Eval fixture | Eval subsystem | Usually yes | Offline after redaction. |

## Trusted Context Contract

Every runtime operation should carry:

```json
{
  "trace_id": "uuid",
  "tenant_id": "uuid",
  "actor_type": "user|tenant_admin|operator|adapter|worker|tool",
  "actor_id": "stable-redacted-id",
  "platform": "telegram|discord|null",
  "channel_id": "string|null",
  "thread_id": "string|null",
  "run_id": "uuid|null"
}
```

Rules:

- `tenant_id` is immutable after context creation.
- `trace_id` is generated at ingress if absent.
- Internal services accept typed context, not arbitrary tenant id strings.
- Public DTOs must not let clients override trusted context fields.

## Memory Taxonomy

Do not use one generic memory bucket.

| Memory type | Storage | Prompt access | Notes |
| --- | --- | --- | --- |
| Runtime state | LangGraph checkpointer + run records | Direct while bounded | Current graph only. |
| Recent conversation | Chat events + summaries | Bounded summary/direct | Tenant-scoped, retention controlled. |
| Tenant config/policy | PostgreSQL | Hydrated summary | Versioned and audited. |
| Knowledge memory | pgvector or Qdrant behind provider | Retrieved with citations | Approved sources only. |
| Workflow state | PostgreSQL | Service-shaped summary | Not scratch files. |
| Member profile | PostgreSQL later | Restricted summary | Needs privacy policy. |
| Tool/plugin memory | Manifest/config tables | Allowed specs only | No raw secrets. |
| Audit/replay | PostgreSQL + traces | Not prompt by default | Incident evidence. |
| Secret handles | Secret manager/encrypted handles | Never | Resolve after permission check. |

## Isolation Invariants

- A user from Tenant A cannot list, query, retrieve, or infer Tenant B data.
- A tenant-disabled runtime cannot keep using stale cached permissions.
- A tool cannot execute with a credential handle not scoped to the current tenant/capability.
- A vector query without tenant filter is a bug, not an optimization.
- A model output cannot create trusted tenant context, policy, credential, or profile memory directly.
- A trace export is not a compliance audit record.

## Open Design Decisions

- Should v1 tenant admin auth be JWT user-to-tenant membership, API keys, or both?
- Should knowledge RAG start with template pgvector or add Qdrant immediately behind a provider contract?
- Which retention period applies to chat events and moderation history?
- Which roles can approve candidate knowledge?
- How should tenant deletion propagate to vectors, checkpoints, eval traces, and observability exports?
