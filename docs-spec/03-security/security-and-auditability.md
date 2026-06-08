# Security And Auditability

Controls, audit requirements, moderation safety, compliance guardrails. Threat catalog: [threat-model.md](threat-model.md). Auth: [authn-authz.md](authn-authz.md). Secrets: [secret-handling.md](secret-handling.md).

## Đối tượng đọc

Security reviewer, backend engineer, AI engineer, operator, compliance owner, incident responder.

## Tenant Isolation Controls

### PostgreSQL (ADR-002)
RLS toàn diện cho mọi tenant-owned table. Per table:
- `tenant_id` column.
- `ENABLE` + `FORCE ROW LEVEL SECURITY`.
- Policy `USING` + `WITH CHECK` trên `current_setting('app.current_tenant')`.
- Tests dùng least-privileged `app_user` (không owner/superuser/BYPASSRLS).
- Migration downgrade reversible.

SQL pattern: [../02-persistence/migration-rules.md](../02-persistence/migration-rules.md). RLS preferred vì bắt được missed application predicate.

### Vector / Qdrant (ADR-001)
Qdrant không có RLS → app-layer enforcement:
- Knowledge vector payload có tenant_id, source_id, source_version, visibility, active/tombstone, citation metadata.
- Query contract require tenant_id + visibility policy. Thiếu tenant filter = fail closed.
- Public support không retrieve private/internal chunks trừ policy.
- Raw chat/profile/moderation/tool/audit không vào RAG by default (PRD-010).

### Cache & Queue
- Cache keys include tenant/user/session scope.
- Outbox envelopes có tenant_id + trace_id.
- Workers reload tenant status + policy trước processing.
- Backpressure → controlled failures, không silent drop.

## Authentication & Authorization

Tóm tắt (đầy đủ ở [authn-authz.md](authn-authz.md)):
- User token → human account.
- Session token → scope chat một conversation.
- `tenant_memberships` → user → tenant role.
- Adapter credential → platform event → allowed platform/workspace/channel.
- Service principals → automation/CI.
- Operator role → BYPASSRLS + audit.

Roles: tenant_admin, tenant_moderator, platform_operator, service_worker.

## Secret Handling (ADR-006)

Allowed: `credential_handle`, KMS envelope encryption records, redacted summaries/hashes.

Forbidden: raw bot tokens trong config; provider API keys trong plugin config; secrets trong prompt/logs/traces/metrics labels/queue payloads/eval reports; broad platform tokens tới MCP servers.

Credential-like input reject trước persistence. Redaction = defense-in-depth, không phải primary control. Chi tiết: [secret-handling.md](secret-handling.md).

## Tool & Capability Safety

Predicate (mọi capability attempt):
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

Mọi denial audited.

## Moderation Safety

| Mode | Behavior |
| --- | --- |
| Shadow | Record decision only. |
| Propose | Create review/action proposal (Telegram bot review Phase 6). |
| Enforce | Execute allowed action sau policy/idempotency checks. |

Default: support answers warn/refuse; destructive moderation bắt đầu shadow; enforce cần explicit policy per tenant/category/action.

Moderation audit record: tenant id, platform, channel/thread, message id; category, confidence, detector/model/rule version; policy version + mode; proposed + final action; reviewer/approval; platform API response/failure; idempotency key.

## Audit Model

Append-oriented, durable. **Never auto-delete** (retention floor 2y, ADR Decision 13).

Event classes: tenant created/updated/disabled; adapter credential created/rotated/revoked; platform mapping changed; knowledge source created/synced/activated/tombstoned; candidate approved/rejected; plugin/capability enabled/disabled; tool call allowed/denied/executed/failed; moderation decision/proposal/enforcement; model/provider policy changed; operator incident access.

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
No raw secrets trong before/after snapshots.

## Observability Privacy

Production redaction policy (ADR-007):
- Redact secrets/credential-like fields trước trace export.
- Hash/pseudonymize platform user ids trong external traces.
- Avoid full private docs + full chat transcripts trong logs.
- Sampling cho production LLM traces.
- Internal audit tables = source of truth.

## Security Validation Gates

Xem [threat-model.md](threat-model.md) → Validation Gates. Tóm tắt: cross-tenant DB/vector denial, disabled capability, missing credential, secret scan, prompt injection, moderation regression, RLS under least-priv role, redaction tests, migration up/down.

## Incident Response

```text
1. Start từ trace id / platform message id.
2. Load chat event, agent run, run steps, tool calls, retrieval summary, moderation, audit.
3. Confirm tenant config/policy/source/tool versions @ run time.
4. Replay với mocked model/tool outputs.
5. Classify root cause: retrieval|prompt|model|policy|tool|adapter|auth|data.
6. Patch + add regression fixture.
7. Record incident note + operator actions (audit).
```

Detailed runbooks: [../04-observability/runbooks.md](../04-observability/runbooks.md).

## Resolved Open Questions

- Secrets manager → KMS envelope + Postgres credential table (ADR-006), GCP Cloud KMS (ADR-008).
- Isolation → RLS (ADR-002).
- Trace backend → Langfuse self-host after redaction (ADR-007).
- Retention window → audit 2y, chat 90d, moderation 1y (Decision 13).
- Moderation approval UX → Telegram bot review Phase 6.

## References

- [Threat Model](threat-model.md)
- [Authn/Authz](authn-authz.md)
- [Secret Handling](secret-handling.md)
- [ADR-006 Secret Manager](../06-decisions/adr-006-secret-manager.md)
