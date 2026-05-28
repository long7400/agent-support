# Coding Rules

## Principles

- Prefer boring, typed, observable code.
- Keep adapters thin.
- Keep tenant boundaries explicit.
- Test isolation before feature polish.
- Do not hide LLM/tool behavior behind untraceable abstractions.

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

## Python Rules

- Use typed functions for service and domain code.
- Use Pydantic models for API and message contracts.
- Use SQLAlchemy or SQLModel consistently; do not mix persistence styles casually.
- Keep DB access in repository modules.
- Keep business rules in domain or service modules, not route handlers.
- Route handlers validate auth, parse request, call service, return response.
- Every external call has timeout and structured error handling.

## Agent Rules

- Every LangGraph node is a small pure-ish function where possible.
- Nodes receive and return explicit state updates.
- Graph state must be serializable.
- LLM calls are wrapped so tests can mock them.
- Tool calls go through permission checks.
- Prompts are versioned and tested with fixtures.
- No destructive action is emitted directly from the LLM.

## Tenancy Rules

- Every tenant-owned DB table has `tenant_id`.
- RLS is required for tenant-owned tables.
- Tenant id must come from trusted auth/context, not request body alone.
- Background jobs must verify tenant status before processing.
- Vector queries must include tenant filter.
- Logs must include tenant id and trace id, but never secrets.

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
