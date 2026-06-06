# Agent Support — AI Agent Guide

## Stack
Python 3.13, FastAPI >=0.121, LangGraph >=1.0, LangChain >=1.0, Langfuse 3.9.1, Pydantic v2, SQLAlchemy 2 + asyncpg/psycopg, Alembic, PostgreSQL/pgvector, Qdrant, Valkey/Redis, structlog, slowapi, Prometheus/Grafana. Package manager: `uv`.

## Source of Truth
- Root `AGENTS.md` is canonical for agents; read `rules/project-main-rules.mdc` only for deeper conventions.
- Numbered docs `docs/00-foundation`..`docs/07-onboarding` and `docs/api-reference` win over legacy root docs and root `README.md`.
- Entry points: `app/main.py` (FastAPI), `app/api/v1/`, `app/core/langgraph/graph.py`, `app/worker.py`, `alembic/`.

## Commands
```bash
make install       # uv sync + pre-commit install
make dev           # uvicorn app.main:app --reload --port 8000
uv run pytest      # tests (or: uv run pytest tests/test_p0_infra.py)
make lint          # ruff check .
uv run ruff format --check .
make typecheck     # pyright standard mode
make check         # lint + typecheck
make docker-compose-up ENV=development  # full local stack
make migrate       # alembic upgrade head
```

## Patterns
```python
@router.post("/chat", response_model=ChatResponse)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["chat"][0])
async def chat(request: Request, chat_request: ChatRequest,
               session: Session = Depends(get_current_session)):
    logger.info("chat_request_received", session_id=session.id,
                message_count=len(chat_request.messages))
    result = await agent.get_response(chat_request.messages, session.id,
                                      user_id=str(session.user_id), username=session.username)
    return ChatResponse(messages=result)
```

## Always
- Keep imports at file top; type-hint all functions; use Pydantic DTOs at API boundaries.
- Use async for DB/LLM/network I/O; use dependency injection for routes/services.
- Add `@limiter.limit(...)` to every route; keep database operations async.
- Use structlog events as `lowercase_with_underscores`; pass context as kwargs.
- Use `logger.exception()` for exceptions and tenacity for retries.
- Validate tenant/security boundaries early; tenant-owned tables need RLS + denial tests.

## Never
- Never log secrets, tokens, PII, raw private docs, or unredacted traces.
- Never use f-strings as structlog event names; never cache errors.
- Never call real LLMs/external tools in unit tests; use fake fixtures.
- Never return ORM objects directly from API routes or bypass tenant policy/tool interfaces.
- Never hardcode secrets or commit `.env*` files.

## Testing
Tests live in `tests/` (`pytest`). Current baseline: `tests/test_p0_infra.py`. Unit tests have no DB/network/real LLM; integration tests cover API/DB. Release gates include ruff, pyright, pytest, migration downgrade, RLS/vector tenant-denial, redaction tests.

## Glossary
- **Tenant** = crypto project/customer; top isolation unit (docs; runtime model pending).
- **Session** = `app/models/session.py` chat session owned by `User`.
- **Message / ChatRequest** = `app/schemas/chat.py` API conversation DTOs.
- **LangGraphAgent** = `app/core/langgraph/graph.py` graph/checkpointer runtime.
- **LLMService** = `app/services/llm/service.py` retry + circular fallback wrapper.
- **MemoryService** = `app/services/memory.py` optional mem0 long-term user memory.
- **KMSProvider** = `app/core/kms.py` secret envelope-encryption interface.
- **Outbox** = planned durable work/delivery tables using `SKIP LOCKED` (ADR-003).

## Git
Branch from `main`; prefer `feat/`, `fix/`, `refactor/`, `docs/` prefixes. Commits follow Conventional Commits (`type(scope): description`). Pre-commit runs hygiene, detect-secrets, ruff lint/format, pyright; never stage unrelated files with `git add .`.

## References

- LangGraph Documentation: https://langchain-ai.github.io/langgraph/
- LangChain Documentation: https://python.langchain.com/docs/
- FastAPI Documentation: https://fastapi.tiangolo.com/
- Langfuse Documentation: https://langfuse.com/docs
