# Coding Rules

These rules are mandatory for production code in this repo. If a rule needs to
change, update `docs/decisions/` first.

## Principles

- Prefer boring, typed, observable code.
- Keep adapters thin.
- Keep tenant boundaries explicit.
- Test isolation before feature polish.
- Do not hide LLM/tool behavior behind untraceable abstractions.
- Use proven framework/library primitives before writing custom infrastructure.
- Make surgical changes. Every changed line should trace to the task.
- Prefer explicit contracts over implicit magic.

## Repository Layout

```text
adapters/
  telegram-bot/
  discord-bot/
core/
  api/
  engine/
  domain/
  persistence/
  workers/
mcp_servers/
data_plane/
infra/
tests/
docs/
```

Ownership:

- `adapters/`: platform translation only. No business logic, no secrets lookup.
- `core/api/`: FastAPI app, routers, dependencies, request/response DTOs.
- `core/domain/`: business rules and pure-ish policy logic.
- `core/persistence/`: SQLAlchemy models, repositories, sessions, migrations, RLS helpers.
- `core/engine/`: LangGraph workflow once agent runtime starts.
- `core/workers/`: background job entrypoints and orchestration.
- `mcp_servers/`: tool boundary implementations.
- `infra/`: local and deployment infrastructure.
- `tests/`: unit and integration tests mirroring code boundaries.

## Python Rules

- Use typed functions for all production code.
- Use Pydantic v2 models for API, message contracts, settings, and validation.
- Use SQLAlchemy 2.x ORM for persistence models and DB access.
- Use Alembic for every schema, role, grant, RLS, and migration change.
- Do not use SQLModel unless a new ADR accepts it for a specific reason.
- Keep Pydantic DTOs separate from SQLAlchemy ORM models.
- Keep DB access in repository/persistence modules.
- Keep business rules in domain or service modules, not route handlers.
- Route handlers validate auth/context, parse request, call service, return response.
- Every external call has timeout, typed errors, and structured logging.
- Prefer framework primitives: FastAPI `APIRouter` and `Depends`, Pydantic validators,
  SQLAlchemy sessions/transactions, Alembic migrations, pytest fixtures, Ruff, mypy.
- Do not hand-roll mini frameworks for validation, routing, migrations, retries,
  background jobs, tracing, or serialization while a project-approved library covers it.

## Dependency Direction

Allowed dependencies:

```text
core/api -> core/domain -> core/persistence
core/api -> core/persistence only through explicit service/repository boundaries
core/workers -> core/domain and core/persistence
adapters -> internal HTTP/API or message envelope contracts
```

Forbidden dependencies:

- `core/domain` importing FastAPI, SQLAlchemy sessions, HTTP clients, or framework state.
- `core/persistence` importing FastAPI routers or request objects.
- route handlers running raw SQL or embedding business rules.
- adapters reading tenant secrets directly.

When in doubt, choose a boring service/repository boundary before inventing abstraction.

## API Contract Rules

- Request/response models live near API boundaries and use Pydantic.
- Name DTOs with clear suffixes: `Request`, `Response`, `Create`, `Update`, `Public`.
- Every public route declares `response_model`.
- API fields use `snake_case`.
- Error responses must use a consistent shape before new API surfaces expand.
- Never return ORM objects directly from public routes.
- Tenant id comes from trusted auth/context, never arbitrary request body fields.

## Agent Rules

- Every LangGraph node is a small pure-ish function where possible.
- Nodes receive and return explicit state updates.
- Graph state must be serializable.
- LLM calls are wrapped so tests can mock them.
- Tool calls go through permission checks.
- Prompts are versioned and tested with fixtures.
- No destructive action is emitted directly from the LLM.
- Agent state must be serializable and replayable.
- LLM/provider calls must be wrapped behind interfaces that tests can mock.

## Tenancy Rules

- Every tenant-owned DB table has `tenant_id`.
- RLS is required for tenant-owned tables.
- Use `ENABLE ROW LEVEL SECURITY` and `FORCE ROW LEVEL SECURITY` for tenant tables.
- RLS policies must include both `USING` and `WITH CHECK` where writes are allowed.
- RLS tests must use the application DB role, not table owner or superuser.
- Tenant id must come from trusted auth/context, not request body alone.
- Application code must set tenant context inside a transaction.
- Background jobs must verify tenant status before processing.
- Vector queries must include tenant filter.
- Logs must include tenant id and trace id, but never secrets.
- Migration downgrade must revoke grants/ownership dependencies before dropping roles.

## Persistence Rules

- SQLAlchemy 2.x mapped models are the persistence source of truth.
- Pydantic schemas are not persistence models.
- Alembic migration files may contain raw SQL for RLS, grants, indexes, and DB-specific
  behavior. Application code should avoid raw SQL unless a repository documents why.
- Do not mix sync `Session` and `AsyncSession` in the same boundary. Current baseline is
  sync SQLAlchemy. Switching to async requires an ADR and benchmark/operational reason.
- Repository methods should accept explicit tenant context or run inside a tenant-scoped
  session helper.
- Migrations must upgrade from empty DB and downgrade cleanly unless the plan explicitly
  documents a forward-only migration.
- Do not make Qdrant, Redis, or TurboVec the source of truth for transactional metadata.

## Vector Search Rules

- All vector search implementations must satisfy one `VectorSearchProvider` contract.
- Qdrant is the durable provider and source of truth.
- TurboVec is optional until ADR 0002 is accepted.
- Accelerator indexes must be rebuildable from durable data.
- Accelerator indexes must be feature-flagged.
- Provider results must include score, chunk id, source id, document id, and citation metadata.
- Provider tests must cover tenant filters, source filters, empty filters, deleted chunks, persist/load, and fallback.

## MCP Tool Rules

- Tool names use namespace format: `domain.action`.
- Tool inputs and outputs have schemas.
- Tool execution has timeout.
- Tool failures return typed errors.
- Tool calls are audited.
- Tool credentials are tenant-scoped.

## Testing Rules

- Unit tests must not call real LLMs.
- Integration tests may use local Docker services.
- Every new table needs migration tests.
- Every new tenant storage path needs cross-tenant denial tests.
- Every new tool needs disabled-tool and timeout tests.
- Every incident fix must add a regression test.
- Tests should prove security boundaries with the least-privileged role.
- Prefer pytest fixtures over shared mutable setup helpers.
- Do not skip integration tests silently. Use explicit env gates and document them.

Mandatory local gates before claiming done:

```text
uv run ruff check .
uv run mypy .
uv run pytest tests/unit
docker compose -f infra/docker-compose.yml up -d --wait
uv run alembic upgrade head
AGENT_SUPPORT_RUN_INTEGRATION=1 uv run pytest tests/integration
uv run python scripts/check_secret_scan.py
```

When migrations change, also run:

```text
uv run alembic downgrade base
uv run alembic upgrade head
```

## Observability Rules

- Every request/event carries `trace_id` and tenant context.
- Every external call logs latency, timeout/error class, and redacted identifiers.
- Every LLM call records provider, model, token usage, and cost estimate when available.
- Every tool call is audited with redacted input/output summary.
- Do not log secrets, credentials, raw tool tokens, or full private source documents.

## Simplicity Rules

- No abstraction for single-use code unless it protects a real boundary.
- No speculative config or feature flags without an accepted plan.
- No custom retry/cache/queue code until the approved library cannot satisfy the need.
- If an implementation feels clever, write the boring version first.
- If a file grows broad responsibilities, split by boundary, not by arbitrary layers.

## Naming Rules

- Python modules: `snake_case.py`.
- Directories: `kebab-case` for JS/TS packages, `snake_case` for Python packages where importable.
- DB tables: plural snake_case.
- API fields: snake_case.
- Redis streams: `{env}:{tenant_scope}:{direction}:{platform}` when tenant-specific, or include tenant in envelope when shared.
- Trace id field: always `trace_id`.

## Commit Rules

- Use conventional commits: `feat:`, `fix:`, `docs:`, `test:`, `chore:`.
- Keep commits scoped and reviewable.
- Run validation before pushing.
- Never commit `.agents/`, `.claude/`, `.codex/`, `plans/`, local env files, or secrets.

## References

- FastAPI app structure: https://fastapi.tiangolo.com/tutorial/bigger-applications/
- FastAPI dependencies: https://fastapi.tiangolo.com/tutorial/dependencies/
- Pydantic v2: https://docs.pydantic.dev/
- SQLAlchemy ORM: https://docs.sqlalchemy.org/en/20/orm/
- Alembic: https://alembic.sqlalchemy.org/
- PostgreSQL RLS: https://www.postgresql.org/docs/current/ddl-rowsecurity.html
- Ruff: https://docs.astral.sh/ruff/
- mypy: https://mypy.readthedocs.io/
