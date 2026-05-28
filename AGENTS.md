# AGENTS.md

This file is the entrypoint for coding agents working in this repository.
Read it before editing files.

## Mission

Agent Support is a tenant-isolated crypto community operations platform. The
platform answers support questions, moderates risky messages, onboards members,
syncs tenant knowledge sources, and audits agent/tool behavior across Telegram
and Discord.

This is not a generic chatbot builder. Tenant isolation, auditability, and
observable agent workflows matter more than fast demos.

## Read First

Use this reading order:

1. `docs/README.md`
2. `docs/production-spec.md`
3. `docs/system-architecture.md`
4. `docs/coding-rules.md`
5. `docs/implementation-flow.md`
6. `docs/validation-checklist.md`
7. Relevant ADRs under `docs/decisions/`

If these docs disagree, prefer the latest ADR, then `docs/coding-rules.md`, then
the implementation plan for the current task.

## Current Stack

- Python 3.14
- FastAPI for the control plane
- Pydantic v2 for settings, API DTOs, message contracts, and validation
- SQLAlchemy 2.x for ORM persistence
- Alembic for migrations, roles, grants, and RLS SQL
- PostgreSQL with RLS for tenant-owned metadata
- Redis for future streams/jobs
- Qdrant for future durable vector storage
- LangGraph and MCP later, not in the foundation slice

Do not introduce SQLModel unless a new ADR accepts it.

## Operating Rules

- Think before coding. Restate the target, touchpoints, acceptance criteria, and
  validation commands before broad changes.
- Keep changes surgical. Do not refactor unrelated files.
- Prefer boring framework/library primitives over custom machinery.
- Use typed code. Keep `uv run mypy .` green.
- Keep tenant boundaries explicit. No tenant id from untrusted request bodies.
- Keep adapters thin. They translate platform events into internal envelopes.
- Keep domain code framework-free.
- Keep DB access in persistence/repository modules.
- Keep route handlers thin: auth/context, validation, service call, response.
- Never hide LLM/tool behavior behind untraceable abstractions.
- Never commit local agent/tooling state, env files, or secrets.

## Architecture Boundaries

Allowed direction:

```text
adapters -> core/api or message envelopes
core/api -> service/domain
core/domain -> pure business rules
core/persistence -> SQLAlchemy models, repositories, sessions, migrations
core/workers -> service/domain/persistence
mcp_servers -> typed tool boundary
```

Forbidden:

- `core/domain` importing FastAPI or SQLAlchemy sessions.
- route handlers running raw SQL.
- adapters reading tenant secrets directly.
- persistence modules calling platform APIs.
- business logic inside Alembic migrations.
- RAG or agent code bypassing tenant filters.

## Persistence Rules

- SQLAlchemy models are persistence models.
- Pydantic models are API/config/contract models.
- Alembic owns all schema changes.
- Raw SQL belongs in migrations or tightly documented repository methods.
- Every tenant-owned table needs `tenant_id`, RLS policy, and isolation tests.
- RLS tests must use the app DB role, not owner/superuser.
- When migrations change, prove both upgrade and downgrade.

## Testing And Validation

Run these before claiming done:

```bash
uv run ruff check .
uv run mypy .
uv run pytest tests/unit
docker compose -f infra/docker-compose.yml up -d --wait
uv run alembic upgrade head
AGENT_SUPPORT_RUN_INTEGRATION=1 uv run pytest tests/integration
uv run python scripts/check_secret_scan.py
```

When migrations change:

```bash
uv run alembic downgrade base
uv run alembic upgrade head
```

For API runtime smoke:

```bash
uv run uvicorn core.api.main:app --host 127.0.0.1 --port 8000
curl http://127.0.0.1:8000/healthz
```

## Code Quality Bar

- Small modules with one clear responsibility.
- No speculative abstraction.
- No duplicated tenant isolation checks hidden across layers.
- No unbounded external calls.
- No logs containing secrets or full private tenant data.
- Tests should prove behavior, not implementation trivia.
- Docs must change when commands, contracts, schemas, or boundaries change.

## Implementation Workflow

1. Read the current plan or create one before implementation.
2. Inspect existing code and docs.
3. Add or update tests first when behavior/security boundary changes.
4. Implement the smallest vertical slice.
5. Run validation.
6. Update docs and ADRs if decisions changed.
7. Report exact commands and results.

## Local Files To Avoid

Do not commit or depend on:

- local agent/tooling state directories
- virtualenv directories
- scratch plans
- local env files
- Docker volumes or generated caches

## Reference Inspiration

This file follows the same spirit as the referenced `CLAUDE.md`: think clearly,
prefer simple maintainable code, work from evidence, and verify before claiming
completion. This repo's project-specific source of truth remains `docs/`.
