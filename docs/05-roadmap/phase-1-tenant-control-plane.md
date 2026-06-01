# Phase 1: Tenant Control Plane

**Goal:** create tenant SaaS spine với RLS isolation từ table đầu tiên.

## Scope

- `tenants`, `tenant_memberships`, `tenant_roles`, `service_principals`, `tenant_config_versions`.
- PostgreSQL RLS toàn diện (ADR-002) — pattern set up 1 lần, mọi phase sau hưởng.
- Tenant-aware auth dependencies (JWT user + membership; service principals).
- Admin/operator APIs cho tenant lifecycle.
- Audit events cho config mutation.

## Deliverables

### Schema + RLS (ADR-002)
- Tables theo [schema-reference.md](../02-persistence/schema-reference.md) → Tenant & Auth group.
- Per table: `ENABLE` + `FORCE ROW LEVEL SECURITY`, policy `USING`+`WITH CHECK`, GRANT `app_user`.
- Roles: `app_user` (no BYPASSRLS), `app_operator` (BYPASSRLS).
- Helper `with_tenant_context()`: `async with db.begin()` + `SET LOCAL app.current_tenant`.
- Alembic raw SQL cho RLS policies.

### Auth (ADR-005)
- `get_current_tenant_member(tenant_id)` dependency: JWT → membership → role.
- Service principal auth (hashed key, scopes).
- Operator role gate cho cross-tenant operations.
- Tenant context resolution flow (xem [authn-authz.md](../03-security/authn-authz.md)).

### Admin/Operator API
- `POST /v1/admin/tenants` (operator) — create tenant.
- `GET/PATCH /v1/admin/tenants/{id}` — config (versioned).
- `POST /v1/admin/tenants/{id}/members` — invite/assign role.
- `POST /v1/admin/tenants/{id}/service-principals` — generate API key (show once).
- Tenant status transitions (active/disabled/suspended/deleting).
- Full contracts: [admin-api.md](../api-reference/admin-api.md).

### Audit
- `audit_events` table.
- Config mutation → audit (actor, trace_id, before/after summary, config_version).

## Exit Criteria

- [ ] Tenant A cannot read/write Tenant B data (RLS test under `app_user`).
- [ ] Config mutations audited.
- [ ] Disabled tenant cannot be used for runtime.
- [ ] Migration upgrade/downgrade passes.
- [ ] Service principal scope enforced.
- [ ] Operator access produces audit row.

## Validation

```bash
make migrate
make migrate-downgrade
make migrate
pytest tests/isolation     # cross-tenant denial
pytest tests/auth          # membership + service principal
```

Cross-tenant denial test (critical):
```python
# As app_user, SET LOCAL tenant=A, SELECT from tenant B rows -> 0 rows.
# INSERT with tenant_id=B while context=A -> RLS violation (WITH CHECK).
```

## Risks

| Risk | Mitigation |
| --- | --- |
| `SET LOCAL` outside transaction → leak | Helper enforces `db.begin()`; lint/review gate. |
| Forgot `FORCE ROW LEVEL SECURITY` | Migration checklist; isolation test catches. |
| App connection uses owner role | Config uses `app_user` only; pre-flight check. |

## References

- [ADR-002 Tenant Isolation](../06-decisions/adr-002-tenant-isolation-model.md)
- [ADR-005 Tenant Auth Model](../06-decisions/adr-005-tenant-auth-model.md)
- [Migration Rules](../02-persistence/migration-rules.md)
- [Admin API](../api-reference/admin-api.md)
