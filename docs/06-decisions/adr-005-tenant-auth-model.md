# ADR-005: Tenant Admin Auth Model

- **Status:** accepted
- **Date:** 2026-06-01
- **Deciders:** eng-lead, security-reviewer, backend-eng
- **Related:** PRD-012, [authn-authz.md](../03-security/authn-authz.md)

## Context

Template có JWT user + session. Cần cách tenant admin authenticate vào admin API (configure source, policy, tools, persona). Adapter principal đã tách riêng. Audit cần phân biệt actor (human vs machine).

## Decision

**JWT user (human) + `tenant_memberships` cho human admin, service principals (API keys) cho automation.** OAuth/SSO defer Phase 7.

## Consequences

### Positive
- Tách rõ human admin vs machine automation → audit có actor_type.
- 1 user là admin nhiều tenant với role khác nhau.
- CI/CD dùng service principal (scoped).

### Negative / Costs
- 2 auth path (build cả 2).
- Cần admin UI/CLI để invite members + generate keys.

### Follow-up actions
- `tenant_memberships(user_id, tenant_id, role)` + `tenant_roles` (Phase 1).
- `service_principals(tenant_id, key_hash, scopes)` — show key once.
- `get_current_tenant_member(tenant_id)` dependency.
- Audit `actor_type` phân biệt human/service/adapter/operator.

## Alternatives Considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| JWT user + memberships only | Reuse template auth | Không hợp automation/CI | rejected (insufficient) |
| API keys per tenant only | Đơn giản, CI-friendly | Không phân biệt actor (audit blur), no session revoke | rejected |
| **JWT user + service principals + memberships** | Human/machine tách, audit actor | 2 path build | **chosen** |
| OAuth/SSO (Google/GitHub) | No password mgmt | Setup phức tạp MVP | defer Phase 7 |

## Notes

Adapter principal (platform) đã tách (`adapter_credentials` table), không nhầm với admin auth. MVP Phase 1: login email/password → JWT, membership lookup, admin generate service principal cho automation.
