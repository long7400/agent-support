# Security And Auditability

## Mục đích

Tài liệu này định nghĩa threat model, controls, audit requirements, secret handling, moderation safety, và compliance guardrails cho Agent Support.

## Đối tượng đọc

Security reviewer, backend engineer, AI engineer, operator, compliance owner, và incident responder.

## Security Principles

- Deny by default.
- Tenant context is trusted only after authentication and mapping.
- Model output is untrusted until policy checked.
- Tool output is untrusted until schema-validated and redacted.
- Secrets are handles, not prompt/log/config values.
- Audit evidence is durable and internal; traces are observability artifacts.
- Every destructive action needs policy, idempotency, and audit.

## Main Threats

| Threat | Example | Required control |
| --- | --- | --- |
| Tenant spoofing | Adapter body includes another tenant id | Ignore request tenant id; resolve through adapter principal and platform mapping. |
| Cross-tenant SQL leak | Missing tenant predicate | RLS or equivalent least-privilege isolation, tests with non-owner role. |
| Cross-tenant vector leak | Query lacks tenant filter | Central vector provider requiring tenant/source/visibility filters. |
| Prompt injection | User/source tells model to ignore policy | Treat retrieved/user/tool text as data; policy and tool checks outside prompt. |
| Tool privilege escalation | Model asks disabled tool | Filtered tool specs and runtime re-check before call. |
| MCP confused deputy | Broad token passed to remote server | Tenant-scoped credential handles; no token passthrough; pinned server identity. |
| Secret leakage | API key in plugin config/logs | Reject raw credentials; redact defense-in-depth; secret scan. |
| False moderation enforcement | LLM incorrectly bans user | Shadow/propose default; enforce only by policy; review and rollback path. |
| Trace privacy leak | Full private docs in Langfuse | Redaction/sampling/export policy; durable audit summary internal. |
| Cost/DoS | Agent loops tools/models | Step limits, timeouts, budgets, rate limits, queue backpressure. |

## Authentication And Authorization

Template provides JWT users and session-scoped chat tokens. Agent Support needs tenant-aware authorization on top:

- User token authenticates a human account.
- Session token scopes chat to one conversation.
- Tenant membership maps user to tenant role.
- Adapter token or credential maps platform event to allowed platform/workspace/channel.
- Service identities authorize workers and internal jobs.

Minimum production roles:

| Role | Scope |
| --- | --- |
| Tenant admin | Own tenant config, sources, policy, tools. |
| Tenant moderator | Review candidates, moderation proposals, false positives. |
| Platform operator | Tenant lifecycle, incident review, operational controls. |
| Service worker | Runtime/sync/tool execution within policy. |

## Tenant Isolation Controls

### PostgreSQL

Use Alembic for all schema, grants, and RLS/equivalent SQL.

For every tenant-owned table:

- `tenant_id` or equivalent ownership column.
- Policy for read/write isolation.
- `WITH CHECK` equivalent on writes.
- Tests using least-privileged runtime role, not owner/superuser.
- Migration downgrade or documented forward-only rollback.

If the team chooses not to use PostgreSQL RLS in the template, document the equivalent isolation model before feature work:

- separate app roles or schemas,
- mandatory repository/session tenant filters,
- policy tests that prove cross-tenant denial,
- code review gate for every query path.

RLS is preferred because it catches missed application predicates.

### Vector And Memory Stores

Template has pgvector-backed mem0 memory. Product knowledge retrieval must not rely on user-level mem0 isolation alone.

Rules:

- Knowledge vector payload includes tenant id, source id, source version, visibility, active/tombstone state, citation metadata.
- Query contract requires tenant id and visibility policy.
- Public support cannot retrieve private/internal chunks unless tenant policy permits.
- Raw chat/profile/moderation/tool/audit data does not enter RAG by default.

### Cache And Queue

- Cache keys include tenant/user/session scope.
- Queue envelopes include tenant id and trace id even when stream/topic is tenant-scoped.
- Workers reload tenant status and policy before processing.
- Backpressure returns controlled failures instead of dropping work silently.

## Secret Handling

Allowed:

- `credential_handle`
- secret manager references
- encrypted credential records with scoped decrypt policy
- redacted summaries and hashes

Forbidden:

- raw bot tokens in tenant config
- provider API keys in plugin config
- secrets in model prompt context
- secrets in logs, traces, metrics labels, queue payloads, eval reports
- broad platform tokens sent to MCP servers

Credential-like input should be rejected before persistence. Redaction is defense-in-depth, not the primary control.

## Tool And Capability Safety

Every capability attempt must pass this predicate:

```text
tenant active
and plugin/capability enabled
and agent role allowed
and risk level allowed
and input schema valid
and budget/rate limit available
and timeout configured
and credential handle available when required
and approval gate satisfied when required
```

Denied outcomes:

| Condition | Error | Execution |
| --- | --- | --- |
| Unknown tool | `TOOL_NOT_FOUND` | No |
| Disabled plugin | `PLUGIN_DISABLED` | No |
| Disabled capability | `CAPABILITY_DISABLED` | No |
| Invalid input | `TOOL_INPUT_INVALID` | No |
| Missing credential | `TOOL_CREDENTIAL_UNAVAILABLE` | No |
| Timeout | `TOOL_TIMEOUT` | Partial/no, redacted |
| Over budget | `TOOL_POLICY_DENIED` | No |
| Output invalid | `TOOL_OUTPUT_INVALID` | Fail closed |

All denials are audited.

## Moderation Safety

Modes:

| Mode | Behavior |
| --- | --- |
| Shadow | Record decision only. |
| Propose | Create review/action proposal. |
| Enforce | Execute allowed action after policy/idempotency checks. |

Default:

- Support answers can warn/refuse.
- Destructive moderation starts in shadow.
- Enforce requires explicit policy by tenant/category/action.

Moderation audit record should include:

- tenant id, platform, channel/thread, message id
- category, confidence, detector/model/rule version
- policy version and mode
- proposed action and final action
- reviewer/approval if any
- platform API response or failure summary
- idempotency key

## Audit Model

Audit records must be append-oriented and durable.

Minimum audit event classes:

- tenant created/updated/disabled
- adapter credential created/rotated/revoked
- platform mapping changed
- knowledge source created/synced/activated/tombstoned
- candidate approved/rejected
- plugin/capability enabled/disabled
- tool call allowed/denied/executed/failed
- moderation decision/proposal/enforcement
- model/provider policy changed
- operator incident access

Common fields:

```json
{
  "trace_id": "uuid",
  "tenant_id": "uuid|null",
  "actor_type": "tenant_admin|moderator|operator|adapter|worker|tool",
  "actor_id": "stable-redacted-id",
  "action": "stable.action.name",
  "resource_type": "string",
  "resource_id": "string",
  "before_summary": {},
  "after_summary": {},
  "redaction_applied": true,
  "created_at": "timestamp"
}
```

Do not store raw secrets in before/after snapshots.

## Observability Privacy

Template includes Langfuse, Prometheus, Grafana, structured logs, and request ids. Production Agent Support must add tenant-aware redaction policy:

- Redact secrets and credential-like fields before trace export.
- Hash or pseudonymize platform user ids in external traces.
- Avoid full private docs and full chat transcripts in logs.
- Use sampling for production LLM traces.
- Keep internal audit tables as source of truth.

## Security Validation Gates

Before production enablement:

- Cross-tenant DB denial tests.
- Cross-tenant vector denial tests.
- Disabled capability tests.
- Missing credential tests.
- Secret scan.
- Prompt injection fixtures.
- Moderation false positive/negative regression fixtures.
- RLS or equivalent isolation tests under least-privileged role.
- Trace/log redaction tests.
- Migration upgrade/downgrade tests.

## Incident Response

Incident workflow:

1. Start from trace id or platform message id.
2. Load chat event, agent run, run steps, tool calls, retrieval context summary, moderation records, and audit events.
3. Confirm tenant config/policy/source/tool versions at run time.
4. Replay with mocked model/tool outputs when possible.
5. Classify root cause: retrieval, prompt, model, policy, tool, adapter, auth, or data issue.
6. Patch behavior and add regression fixture.
7. Record incident note and operator actions.

## Open Questions

- Which production secrets manager is accepted?
- Will production use RLS, separate tenant schemas, or another enforced model?
- Which trace backend can receive tenant-sensitive data after redaction?
- What is the required retention window for audit, chat, moderation, and eval artifacts?
- Which human approval UX is enough before moderation enforcement?
