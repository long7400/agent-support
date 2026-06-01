# Authentication & Authorization

JWT user + tenant role + adapter principal + service principals (ADR-005).

## Auth Model Overview

3 trust paths tách biệt (PRD-012):

| Path | Identity | Use |
| --- | --- | --- |
| **Human admin** | JWT user + `tenant_memberships` role | Admin/operator API (configure source, policy, tools, persona). |
| **Automation** | Service principal (API key, hashed) | CI/CD, programmatic admin theo scope. |
| **Platform adapter** | Adapter principal (credential, scoped) | Submit normalized events cho platform/workspace/channel. |

> Adapter principal ≠ admin credential. Không nhầm 2 path.

## Human Admin Auth (JWT + Memberships)

Reuse template JWT user. Thêm tenant layer:

```text
login (email/password) -> JWT user token
-> tenant_memberships(user_id, tenant_id, role) lookup
-> role-scoped access to that tenant's resources
```

- 1 user có thể là member nhiều tenant với role khác nhau.
- Roles: `admin`, `moderator`, `viewer` (per tenant).
- Dependency `get_current_tenant_member(tenant_id)` resolve role + set tenant context.
- OAuth/SSO (Google/GitHub) defer Phase 7.

### Role Matrix

| Role | Scope |
| --- | --- |
| Tenant admin | Own tenant config, sources, policy, tools, adapter setup. |
| Tenant moderator | Review candidates, moderation proposals, false positives. |
| Tenant viewer | Read-only dashboards. |
| Platform operator | Tenant lifecycle, incident review, operational controls (cross-tenant, audited). |
| Service worker | Runtime/sync/tool execution trong policy (internal identity). |

## Service Principals (Automation, ADR-005)

```text
service_principals(id, tenant_id, name, key_hash, scopes[], status, last_used_at)
```

- API key generate bởi tenant admin, hiển thị 1 lần, lưu `key_hash` (không raw).
- Scope-limited (vd `source:write`, `capability:read`).
- Audit `actor_type=service_principal` (phân biệt human vs machine — yêu cầu audit).
- Revoke qua status. Rotate qua new key + revoke old.

## Adapter Principal (Platform)

```text
adapter_credentials(id, tenant_id, platform, allowed_channel_patterns[],
                    credential_handle, credential_version, status, last_rotated_at)
```

- Adapter authenticate qua credential (handle, KMS-backed).
- Backend so adapter principal scope vs `tenant_platforms` mapping.
- No trusted tenant id từ adapter body — resolve qua mapping.
- Telegram webhook: `secret_token` per bot verify mọi inbound (ADR-009).
- Logs có credential id/version, never secret.
- Production reject local/demo adapter secrets (PRD-013).

## Operator Role (DB-Level, ADR-002)

```sql
CREATE ROLE app_operator WITH LOGIN BYPASSRLS;
```

- Dùng cho incident response cross-tenant.
- Truy cập qua operator API only, không direct DB.
- **Mọi operator access audited** (`audit_events`, `actor_type=operator`, incident note).
- App runtime KHÔNG dùng role này (dùng `app_user` không BYPASSRLS).

## Tenant Context Resolution Flow

```text
Request
-> authenticate (JWT | service principal key | adapter credential)
-> resolve tenant_id (membership | principal scope | platform mapping)
-> verify role/scope allows action
-> SET LOCAL app.current_tenant (trong transaction)
-> proceed (RLS enforces row visibility)
```

`tenant_id` immutable sau resolution. Public DTO không cho override.

## Token & Secret Handling

- JWT secret, DB passwords → env / secret manager (ADR-006), không hardcode.
- Service principal keys → hashed at rest.
- Adapter/bot tokens → KMS envelope (credential handle).
- Production pre-flight: reject dev/local secrets + demo auth shortcuts (PRD-013).

## Validation

- Cross-tenant access denial: user của tenant A không access tenant B resources.
- Adapter credential reject missing/wrong/scope mismatch.
- Service principal scope enforcement.
- Operator access produces audit row.
- Webhook secret_token mismatch → 401 + audit.
- Production rejects local secrets.

## Resolved Decision

ADR-005: JWT user (human) + service principals (automation) + `tenant_memberships`. OAuth/SSO defer Phase 7. API-keys-only rejected (blur human/machine audit boundary).

## References

- [Security And Auditability](security-and-auditability.md)
- [Secret Handling](secret-handling.md)
- [ADR-005 Tenant Auth Model](../06-decisions/adr-005-tenant-auth-model.md)
- [Migration Rules (RLS roles)](../02-persistence/migration-rules.md)
