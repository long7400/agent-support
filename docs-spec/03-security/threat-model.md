# Threat Model

STRIDE-style threat catalog cho Agent Support. Multi-tenant SaaS → cross-tenant leak là rủi ro #1.

## Security Principles

- Deny by default.
- Tenant context trusted chỉ sau authentication + mapping.
- Model output untrusted cho đến khi policy-checked.
- Tool output untrusted cho đến khi schema-validated + redacted.
- Secrets là handles (KMS envelope), không phải prompt/log/config values.
- Audit evidence durable + internal; traces là observability artifacts.
- Mọi destructive action cần policy + idempotency + audit.

## Threat Catalog

| Threat | STRIDE | Example | Required control |
| --- | --- | --- | --- |
| Tenant spoofing | Spoofing | Adapter body chứa tenant id khác | Ignore body tenant id; resolve qua adapter principal + platform mapping (PRD-001). |
| Cross-tenant SQL leak | Info Disclosure | Query thiếu tenant predicate | PostgreSQL RLS + FORCE + least-privileged role; cross-tenant denial test (ADR-002). |
| Cross-tenant vector leak | Info Disclosure | Qdrant query thiếu tenant filter | `VectorSearchProvider` mandatory tenant filter (app-layer); release gate test (ADR-001). |
| Checkpointer leak | Info Disclosure | LangGraph checkpoint đọc tenant khác | tenant_id trong checkpoint metadata + app-side filter (ADR-002). |
| Prompt injection | Tampering | User/source bảo model ignore policy | Treat retrieved/user/tool text là data; policy + tool checks ngoài prompt; injection eval fixtures. |
| Tool privilege escalation | Elevation | Model gọi disabled tool | Filtered tool specs + runtime re-check trước call. |
| MCP confused deputy | Elevation | Broad token tới remote server | Tenant-scoped credential handles; no token passthrough; pinned server identity. |
| Secret leakage | Info Disclosure | API key trong config/logs/trace | KMS envelope (ADR-006); reject raw credentials; redact; secret scan. |
| Webhook spoofing | Spoofing | Fake Telegram update | secret_token verify per bot; adapter principal scope check. |
| Moderation false enforce | Tampering | LLM ban nhầm user | Shadow/propose default; enforce chỉ policy; review (Telegram bot) + rollback. |
| Moderation callback forgery | Spoofing | Fake approve callback | HMAC signature + verify role (tenant_memberships) + 2FA admin. |
| Trace privacy leak | Info Disclosure | Full private docs vào Langfuse | Redaction callback trước export; sampling; durable audit internal (ADR-007). |
| Cost/DoS | DoS | Agent loop tools/models | Step limits, timeouts, budgets, rate limits, queue backpressure. |
| Outbox poisoning | Tampering | Malformed event lặp lại | Idempotency UNIQUE constraint; retry → DLQ; dead_letter flag (ADR-003). |
| Operator over-reach | Elevation | Operator BYPASSRLS lạm dụng | Audit mọi operator access; separate role; incident note. |
| KMS key compromise | Info Disclosure | Master key leak | GCP KMS IAM scope; DEK rotate; service account JSON ngoài git (ADR-008). |

## Repudiation Coverage

Mọi mutation + capability/action attempt → `audit_events` (append-oriented, durable). Actor type phân biệt human vs machine (ADR-005). Operator incident access audited.

## Attack Surface Map

| Surface | Exposure | Primary control |
| --- | --- | --- |
| `/v1/webhook/telegram/{tenant_id}` | Internet | secret_token + adapter principal |
| `/v1/adapter/ingest` | Internal/adapter | adapter credential scope |
| Admin/operator API | Internet (authed) | JWT + tenant role / operator role |
| Qdrant | Internal network | app-layer tenant filter, no public bind |
| Langfuse | Internal network | redacted ingest, no public bind |
| GCP KMS | API (IAM) | service account least-priv |
| Postgres | Internal network | RLS + role separation |

> v1 single VPS: bind internal services (qdrant, redis, langfuse, postgres) tới localhost/private network only. Chỉ `api` (qua caddy/traefik) expose public.

## Trust Boundaries

```text
[ untrusted ] platform users, message text, retrieved docs, tool outputs, request bodies
     |  (validation + normalization + policy)
[ semi-trusted ] adapter principal (scoped), JWT user (needs membership)
     |  (resolution + role check)
[ trusted ] resolved tenant context, operator session, worker principal
     |  (least-privilege DB role + RLS)
[ secrets ] KMS-backed credential handles (resolve just-in-time, discard)
```

## Validation Gates (Security)

Trước production enablement:
- Cross-tenant DB denial (least-privileged role).
- Cross-tenant vector denial.
- Disabled capability + missing credential tests.
- Secret scan clean.
- Prompt injection fixtures.
- Moderation false positive/negative regression.
- RLS isolation under app_user.
- Trace/log redaction tests.
- Migration upgrade/downgrade.
- Webhook secret_token rejection test.

## References

- [Security And Auditability](security-and-auditability.md)
- [Authn/Authz](authn-authz.md)
- [Secret Handling](secret-handling.md)
- [Runbooks](../04-observability/runbooks.md)
