# Agent Support — AI Agent Guide

## Stack
Python 3.13, FastAPI >=0.121, LangGraph >=1.0, LangChain >=1.0, Langfuse 3.9.1, Pydantic v2, SQLAlchemy 2 async ORM + asyncpg/psycopg, Alembic, PostgreSQL/pgvector, Qdrant, Valkey/Redis, structlog, slowapi, Prometheus/Grafana. Package manager: `uv`.

## Source Of Truth
- Root `AGENTS.md` is canonical for agents; read `rules/project-main-rules.mdc` only for deeper conventions.
- Numbered docs `docs/00-foundation`..`docs/07-onboarding` and `docs/api-reference` win over legacy root docs and root `README.md`.
- Entry points: `app/main.py`, `app/api/v1/`, `app/core/langgraph/graph.py`, `app/worker.py`, `alembic/`.

## Commands
```bash
make install                         # uv sync + pre-commit install
make dev                             # uvicorn app.main:app --reload --port 8000
uv run pytest                        # tests; single file: uv run pytest tests/test_p1_tenant_control_plane.py
make lint                            # uv run ruff check .
uv run ruff format --check .         # formatter gate
make typecheck                       # uv run pyright
make check                           # lint + typecheck
make migrate                         # alembic upgrade head
make docker-compose-up ENV=development
```

## Patterns
```python
@router.post("/{tenant_id}/config", response_model=TenantConfigVersionResponse)
@limiter.limit(settings.RATE_LIMIT_DEFAULT[0])
async def update_config(request: Request, tenant_id: UUID, payload: TenantConfigUpdate,
                        actor: ActorContext = Depends(require_tenant_admin)):
    async with AsyncSessionLocal() as session:
        async with with_tenant_context(session, tenant_id):
            config = await TenantControlPlaneService(session).create_config_version(tenant_id, payload, actor)
            return TenantConfigVersionResponse.model_validate(config)
```

## Always
- Keep imports at file top; type-hint functions; use Pydantic DTOs at API boundaries.
- Use async for DB/LLM/network I/O; use dependency injection for routes/services.
- Add `@limiter.limit(...)` to every route; wrap tenant DB work in `with_tenant_context(...)`.
- Log with structlog `lowercase_with_underscores` events and context kwargs.
- Validate tenant/security boundaries early; tenant tables need RLS + denial tests.

## Never
- Never log secrets, tokens, PII, raw private docs, or unredacted traces.
- Never use f-strings as structlog event names; never cache errors.
- Never call real LLMs/external tools in unit tests; use fake fixtures.
- Never return ORM objects directly from API routes or bypass tenant policy/tool interfaces.
- Never hardcode secrets or commit `.env*` files; never stage unrelated files with `git add .`.

## Testing
Tests live in `tests/` (`pytest`). Current baseline: `test_p0_infra.py`, `test_p1_tenant_control_plane.py`, `test_p1_tenant_isolation.py`. Unit tests avoid DB/network/real LLM; integration tests cover API/DB/RLS. Gates: ruff, ruff format, pyright, pytest, migration downgrade, tenant-denial, redaction.

## Glossary
- **Tenant** = `app/models/tenant.py` crypto project/customer; top isolation unit.
- **TenantMembership** = user -> tenant + role mapping (`admin`, `moderator`, `viewer`).
- **TenantConfigVersion** = immutable persona/links/moderation/model-budget snapshot.
- **ServicePrincipal** = machine identity/API key scoped to tenant automation.
- **AuditEvent** = durable mutation/capability/action record; compliance source of truth.
- **LangGraphAgent** = `app/core/langgraph/graph.py` graph/checkpointer runtime.
- **Outbox** = planned durable work/delivery tables using `SKIP LOCKED`.
- **KMSProvider** = `app/core/kms.py` secret envelope-encryption interface.

## Git
Current branch pattern: `feat/`, `fix/`, `refactor/`, `docs/`; history uses Conventional Commits (`type(scope): description`). Pre-commit enforces hygiene, detect-secrets, ruff lint/format, pyright, and blocks commits to `master`. CI currently runs on PRs and pushes to `master`.

## Broken Windows
- Root `README.md` and legacy `docs/*.md` still describe the inherited template; numbered docs are authoritative.
- CI pushes target `master`, while active work branches from `main` per guide; confirm intended default branch.

## References

- LangGraph Documentation: https://langchain-ai.github.io/langgraph/
- LangChain Documentation: https://python.langchain.com/docs/
- FastAPI Documentation: https://fastapi.tiangolo.com/
- Langfuse Documentation: https://langfuse.com/docs
