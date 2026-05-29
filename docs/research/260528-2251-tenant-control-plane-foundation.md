# Research Report: Tenant Control Plane Foundation

**Date:** 2026-05-28 22:51 +07
**Scope:** prepare Phase 1 after merged infra/FastAPI/RLS foundation.

## Executive Summary

Next phase should be **Tenant Control Plane Foundation**, not messaging, RAG, agent
runtime, or dashboard. The platform now has FastAPI, Postgres, Alembic, and first
RLS proof. The next risk is not missing features; it is letting tenant config,
auth, audit, and DB access patterns grow inside route handlers. Fix that now.

Recommended slice: admin API boundary, consistent error shape, trace context,
repository/service convention, tenant config mutations, tenant plugin enablement,
and append-only audit log. Keep it boring. Do not introduce OAuth, dashboard,
Telegram adapter, LangGraph, Qdrant indexing, or plugin runtime yet.

Brutal truth: `Tenant Control Plane` is the platform's spine. If this phase is
loose, every later subsystem will duplicate tenant checks, invent its own config
loader, and make audit/replay unreliable.

## Research Methodology

- Sources consulted: repo docs/code, `ck:backend-development` references, official
  FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL, OWASP API Security, and
  OpenTelemetry docs.
- Date range: current official docs checked on 2026-05-28.
- Search terms: FastAPI dependencies APIRouter security API key, SQLAlchemy 2.0
  session transaction, PostgreSQL RLS FORCE row security, OWASP API broken object
  authorization, Pydantic settings.
- Gemini: disabled by `.claude/.ck.json`; used WebSearch.

## Codebase Context

Current repo state:

- `main` contains merged infra foundation.
- Stack: Python 3.14, FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic, Postgres RLS.
- Existing DB tables: `tenants`, `chat_events`.
- Existing RLS helper: `core/persistence/rls.py`.
- Existing API route pattern: `core/api/routes/health.py` with `APIRouter`.
- Existing docs mark Phase 1 as Tenant Control Plane.

Relevant planned M1 tasks:

| Task | Current state | Recommendation |
| --- | --- | --- |
| M1-001 `tenants` | Minimal table exists | Extend carefully with config/version fields. |
| M1-002 `tenant_plugins` | Missing | Add now, with RLS and audit. |
| M1-003 RLS helper | Exists | Add API/session dependency pattern. |
| M1-004 audit log | Missing | Add before CRUD spreads. |
| M1-005 admin API auth placeholder | Missing | Add simple header/token guard. |
| M1-006 repository conventions | Missing | Add before more routes. |

## Key Findings

### 1. API Boundary

FastAPI's own structure guidance favors splitting route modules with `APIRouter`
and shared dependencies. This matches the current `core/api/routes` shape.

Recommended API boundary:

```text
core/api/
  dependencies.py       # admin auth, trace id, session deps
  errors.py             # common error shape and handlers
  routes/
    admin_tenants.py
    admin_plugins.py
    admin_audit.py
```

Endpoint shape should stay resource-based:

```text
POST   /admin/tenants
GET    /admin/tenants
GET    /admin/tenants/{tenant_id}
PATCH  /admin/tenants/{tenant_id}
PUT    /admin/tenants/{tenant_id}/plugins/{plugin_name}
DELETE /admin/tenants/{tenant_id}/plugins/{plugin_name}
GET    /admin/audit-log?tenant_id=...
```

Do not add `/createTenant`, `/enablePlugin`, etc. That becomes RPC soup.

### 2. Auth Placeholder

Phase 1 does not need OAuth/JWT. It does need a hard gate so admin routes are
never accidentally public.

Recommended placeholder:

- Header: `X-Admin-Token`.
- Config: `AGENT_SUPPORT_ADMIN_TOKEN`, optional only in local/test.
- Dependency returns `AdminPrincipal`.
- Missing/invalid token returns consistent `401`.
- Audit log stores principal id/type, even if placeholder.

Why not OAuth now:

- No user model yet.
- No dashboard yet.
- OAuth adds token validation, redirect, sessions, scopes, and rotation. YAGNI
  for the next slice.

Upgrade path:

```text
X-Admin-Token placeholder -> admin user/session/JWT -> OAuth/OIDC later
```

### 3. Error Shape

Before adding admin APIs, define one response shape:

```json
{
  "error": {
    "code": "TENANT_NOT_FOUND",
    "message": "Tenant not found",
    "trace_id": "uuid",
    "details": {}
  }
}
```

Use this for auth failures, validation conflicts, not-found, and unexpected errors.
Keep internal exception text out of response bodies.

### 4. Trace Context

Every admin request should have `trace_id`.

Recommended behavior:

- Accept `X-Trace-Id` if valid UUID.
- Generate one if missing.
- Include it in response header and error body.
- Persist it in `audit_log`.

This pays off later when admin config changes affect agent behavior.

### 5. Repository / Service Boundary

The next phase should create the first real pattern:

```text
route -> service -> repository -> SQLAlchemy session
```

Boundary rules:

- Routes parse HTTP/auth and return DTOs.
- Services enforce workflow and audit.
- Repositories own SQLAlchemy statements.
- Domain stays framework-free.
- No route-level raw SQL.
- No Pydantic model reused as ORM model.

This is intentionally small. Do not build a generic repository framework.

### 6. Database Session Strategy

Current foundation has:

- app DB URL for RLS-protected application access.
- admin DB URL for Alembic/migrations.

For Phase 1, separate two flows:

| Flow | DB role/session | Use |
| --- | --- | --- |
| Migration | admin URL | DDL, roles, grants, RLS policy changes. |
| Tenant runtime | app URL + `tenant_session()` | Tenant-scoped reads/writes, RLS proof. |
| Platform admin API | privileged admin session behind auth | Tenant lifecycle/config mutations. |

This is a pragmatic split. Trying to force tenant-scoped RLS into platform-wide
admin CRUD will create awkward policy hacks before the product has real admin
roles. The admin API must compensate with auth, service-level authorization,
audit, and tests.

Later, if tenant-admin self-service is added, introduce a separate tenant admin
authorization model and RLS policy strategy.

### 7. Data Model

Recommended next migration:

```text
tenants
  add display_name text nullable
  add config jsonb not null default '{}'
  add config_version integer not null default 1
  add updated_at timestamptz not null default now()

tenant_plugins
  id uuid pk
  tenant_id uuid not null references tenants(id)
  plugin_name varchar(100) not null
  enabled boolean not null default true
  config jsonb not null default '{}'
  created_at timestamptz not null default now()
  updated_at timestamptz not null default now()
  unique(tenant_id, plugin_name)

audit_log
  id uuid pk
  tenant_id uuid nullable references tenants(id)
  trace_id uuid not null
  actor_type varchar(32) not null
  actor_id varchar(255) not null
  action varchar(100) not null
  resource_type varchar(100) not null
  resource_id varchar(255) not null
  before jsonb nullable
  after jsonb nullable
  created_at timestamptz not null default now()
```

Notes:

- `tenant_plugins` is tenant-owned: RLS required.
- `audit_log` should be append-only from service code.
- Keep `config` JSONB narrow at first. Validate with Pydantic DTOs. Do not turn
  JSONB into a dumping ground.
- Do not add `tenant_platforms` in the same slice unless planning confirms it.

### 8. RLS and Isolation Tests

For every new tenant-owned table:

- `tenant_id` column.
- `ENABLE ROW LEVEL SECURITY`.
- `FORCE ROW LEVEL SECURITY`.
- `USING` and `WITH CHECK` where writes are allowed.
- Tests use app role, not table owner/superuser.

Test cases:

```text
tenant_plugins:
  Tenant A sees only Tenant A plugin rows.
  Tenant A cannot insert Tenant B plugin row.
  Missing tenant context sees zero rows or fails closed.

admin API:
  Missing token -> 401.
  Invalid token -> 401.
  Valid token can mutate tenant config.
  Mutation writes audit row with trace_id.
```

### 9. Backend Security

OWASP API Security aligns with this phase:

- Broken object-level authorization is the main risk for tenant APIs.
- Broken authentication is the main risk for admin endpoints.
- Broken function-level authorization becomes relevant once tenant admins exist.

Minimum controls:

- deny admin routes by default.
- never trust `tenant_id` from arbitrary body fields.
- validate path tenant id against service operation.
- return 404 or 403 consistently; avoid leaking cross-tenant existence.
- no secrets in audit `before/after` JSON.
- parameterized queries only; SQLAlchemy statements or bound `text()`.

### 10. Observability

Keep this tiny:

- `trace_id` on every admin request.
- audit every config mutation.
- structured log line for admin mutation success/failure.
- no OpenTelemetry dependency yet unless a plan accepts it.

OpenTelemetry can come when there are multiple runtime components to correlate.

## Comparative Analysis

### Scope Options

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| Admin auth + tenant/plugins + audit | Builds spine for later phases | Moderate DB/API work | Recommended. |
| Messaging next | Visible demo faster | Tenant/platform config absent | Reject for now. |
| RAG next | Product value faster | Source lifecycle and tenant config absent | Reject for now. |
| Full admin SaaS auth | More realistic production auth | Too much before dashboard/user model | Defer. |

### Auth Options

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| Static `X-Admin-Token` | Simple, testable, enough for local/admin placeholder | Not production auth | Use for this slice only. |
| API key table | Closer to production | Needs secret hashing, rotation, lifecycle | Good next step after placeholder. |
| JWT/OAuth/OIDC | Production-grade direction | Premature without users/dashboard | Defer. |

### Repository Options

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| Simple repository classes/functions | Clear boundary, low overhead | Some repeated query code | Recommended. |
| Generic repository base class | DRY-looking | Hides SQLAlchemy, hard to type well | Reject. |
| Route calls SQLAlchemy directly | Fast | Violates coding rules, hard to audit | Reject. |

## Recommended Design

### Target Slice

Name: `Tenant Control Plane Foundation`

Expected artifacts:

- New research-backed plan.
- Migration `0002_*` for tenant config, `tenant_plugins`, `audit_log`.
- SQLAlchemy models.
- Repository/service modules.
- Admin auth dependency.
- Error and trace helpers.
- Admin route modules.
- Unit and integration tests.
- Docs updates.

### Module Shape

```text
core/
  api/
    dependencies.py
    errors.py
    routes/
      admin_tenants.py
      admin_plugins.py
      admin_audit.py
    schemas/
      tenants.py
      plugins.py
      audit.py
  services/
    tenants.py
    audit.py
  persistence/
    repositories/
      tenants.py
      tenant_plugins.py
      audit_log.py
    models/
      tenant.py
      tenant_plugin.py
      audit_log.py
```

This is enough structure without creating a framework.

### Acceptance Criteria

- Admin routes reject missing/invalid token.
- Tenant create/update works with documented DTOs.
- Plugin enable/disable works and is unique per tenant/plugin.
- Config mutations create audit rows.
- Error response shape is consistent.
- Trace id is generated/preserved and stored in audit.
- RLS isolation tests pass for `tenant_plugins`.
- Alembic upgrade/downgrade works from empty DB.
- Existing validation remains green.

### Out Of Scope

- Telegram/Discord connection runtime.
- Redis Streams.
- LangGraph.
- Qdrant/RAG.
- MCP tool execution.
- Real admin users, OAuth, OIDC, MFA.
- Dashboard UI.
- Billing/quota.

## Implementation Considerations

### DTO Examples

```python
class TenantCreateRequest(BaseModel):
    slug: str
    display_name: str | None = None
    config: TenantConfig = Field(default_factory=TenantConfig)


class TenantResponse(BaseModel):
    id: UUID
    slug: str
    display_name: str | None
    status: Literal["active", "disabled"]
    config_version: int
```

Keep `TenantConfig` small:

```python
class TenantConfig(BaseModel):
    persona: str | None = None
    model_provider: str | None = None
    model_name: str | None = None
```

Do not add every future config field now.

### Audit Actions

Use stable action names:

```text
tenant.created
tenant.updated
tenant.disabled
tenant_plugin.enabled
tenant_plugin.disabled
```

### Validation Commands

```text
uv run ruff check .
uv run mypy .
uv run pytest tests/unit
docker compose -f infra/docker-compose.yml up -d --wait
uv run alembic downgrade base
uv run alembic upgrade head
AGENT_SUPPORT_RUN_INTEGRATION=1 uv run pytest tests/integration
uv run python scripts/check_secret_scan.py
```

## Common Pitfalls

- Treating static admin token as final production auth.
- Letting route handlers run SQLAlchemy queries directly.
- Creating a generic repository abstraction before there are real patterns.
- Allowing tenant id in request body to choose authorization context.
- Forgetting audit before/after redaction.
- Adding `tenant_platforms`, knowledge sources, sync jobs, and tools in one slice.
- Making `config` JSONB unvalidated.
- Testing RLS through owner/superuser and getting false confidence.

## Resources & References

### Official Documentation

- FastAPI bigger applications / `APIRouter`: https://fastapi.tiangolo.com/tutorial/bigger-applications/
- FastAPI dependencies: https://fastapi.tiangolo.com/tutorial/dependencies/
- FastAPI security tools: https://fastapi.tiangolo.com/reference/security/
- Pydantic settings: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- SQLAlchemy session basics: https://docs.sqlalchemy.org/en/20/orm/session_basics.html
- SQLAlchemy transactions: https://docs.sqlalchemy.org/en/20/orm/session_transaction.html
- Alembic operations: https://alembic.sqlalchemy.org/en/latest/ops.html
- PostgreSQL row security policies: https://www.postgresql.org/docs/current/ddl-rowsecurity.html
- OWASP API1 Broken Object Level Authorization: https://owasp.org/API-Security/editions/2023/en/0xa1-broken-object-level-authorization/
- OWASP API2 Broken Authentication: https://owasp.org/API-Security/editions/2023/en/0xa2-broken-authentication/
- OpenTelemetry observability primer: https://opentelemetry.io/docs/concepts/observability-primer/

### Internal References

- `docs/technical-plan.md`
- `docs/task-breakdown.md`
- `docs/system-architecture.md`
- `docs/coding-rules.md`
- `AGENTS.md`

## Next Steps

1. Brainstorm final scope for `Tenant Control Plane Foundation`.
2. Use `/ck:plan` to create phase plan.
3. Implement with TDD bias for auth/error/audit/RLS behavior.
4. Code review before PR.

## Unresolved Questions

- Should Phase 1 include `tenant_platforms`, or keep it for messaging/adapters?
- Should audit reads be platform-admin only in v1, or tenant-admin visible later?
- What exact plugin naming convention should ship first: `rag.search`, `crypto.price`,
  `web.search`, or generic strings with registry validation?
- Should `config_version` increment on every tenant/plugin mutation or only tenant
  config updates?
