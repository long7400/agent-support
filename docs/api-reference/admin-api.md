# Admin API

P1 exposes a minimal tenant control plane under `/api/v1/admin/tenants`.

## Auth

- Operator endpoints require a bearer token matching `OPERATOR_API_KEYS`.
- Tenant admin endpoints require a JWT user with `tenant_memberships.role = admin` for the path tenant.
- Service-principal raw keys are returned only once on create; persisted state stores only hash, prefix, and fingerprint.

## Endpoints

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| POST | `/api/v1/admin/tenants` | Operator | Create tenant, initial config version, and audit event. |
| GET | `/api/v1/admin/tenants/{tenant_id}` | Tenant admin | Read tenant metadata. |
| PATCH | `/api/v1/admin/tenants/{tenant_id}` | Operator | Update metadata/status and audit mutation. |
| POST | `/api/v1/admin/tenants/{tenant_id}/members` | Operator | Add or update tenant membership. |
| POST | `/api/v1/admin/tenants/{tenant_id}/config` | Tenant admin | Create immutable config version and audit mutation. |
| POST | `/api/v1/admin/tenants/{tenant_id}/service-principals` | Tenant admin | Create scoped automation key, shown once. |
| POST | `/api/v1/admin/tenants/{tenant_id}/service-principals/{principal_id}/revoke` | Tenant admin | Revoke automation identity. |

## Deferred

Invitation emails, dynamic permissions, persisted operator roles, rotation history UI, and full tenant deletion propagation are deferred beyond P1.
