# Code Standards

Python/FastAPI + LangGraph. Canonical rules: `AGENTS.md` (workspace root). Đây là phiên bản aligned cho Agent Support rebuild. Khi conflict, `AGENTS.md` wins.

## Language & Runtime

- Python 3.13+, full type hints, must pass `make typecheck` (pyright standard mode).
- async/await cho mọi I/O (DB, LLM, external APIs).
- Pydantic v2 cho validation/DTO; SQLAlchemy 2.0 cho ORM (ADR-004 — tách 2 layer).

## Critical Rules (from AGENTS.md)

### Imports
- **Mọi import ở top of file.** Không import trong function/class.

### Logging (structlog)
- Event name `lowercase_with_underscores` (vd `chat_request_received`).
- **No f-strings trong structlog events** — pass variables as kwargs.
- `logger.exception()` cho exception (giữ traceback), không `logger.error()`.
- Mọi log mang: trace_id, tenant_id, component, status, latency, error_code.

### Retry
- Dùng **tenacity**, exponential backoff. Vd `@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))`.

### Caching
- Chỉ cache successful responses, never errors. Cache keys include tenant scope.

### FastAPI
- Mọi route có rate limiting decorator.
- Dependency injection cho services, DB, auth.
- Mọi DB operation async.
- Tenant context qua `with_tenant_context()` (SET LOCAL, ADR-002).

### Output
- rich library cho formatted console output (progress, tables, panels).

## Code Style

- `async def` cho async operations.
- Functional/declarative; class chỉ cho services và agents.
- File naming: lowercase_with_underscores (`user_routes.py`).
- RORO pattern (Receive Object, Return Object).
- Type hints mọi function signature.

## Error Handling

- Handle errors đầu function (guard clauses, early returns).
- Happy path cuối function.
- `HTTPException` cho expected errors với status code phù hợp.
- Fail closed: thiếu permission/info → deny + audit.

## Database (ADR-002, ADR-004)

- SQLAlchemy 2.0 (`DeclarativeBase`, `Mapped[]`), không SQLModel.
- Tách persistence model khỏi API DTO — không return ORM object trực tiếp.
- Mọi tenant-owned table: `tenant_id` + RLS policy (`ENABLE`+`FORCE`+`USING`+`WITH CHECK`).
- Alembic cho mọi schema change; raw SQL cho RLS/roles/grants/indexes.
- App connection dùng `app_user` (no BYPASSRLS).
- Parameterized queries; `created_at`/`updated_at` trên tables.
- `SET LOCAL app.current_tenant` BẮT BUỘC trong `db.begin()`.

## Security

- Validate input ở boundary (Pydantic).
- Hash passwords (argon2id/bcrypt); hash service principal keys.
- Secrets qua KMS handle (ADR-006), never raw trong config/log/trace/prompt.
- Never log secrets/tokens/PII/full private docs.
- Treat retrieved/user/tool text là untrusted data.

## LangGraph & LLM

- `StateGraph` + Pydantic state schema; `AsyncPostgresSaver` checkpoint.
- Graph nodes gọi service/tool interface, không raw DB/vector client.
- Langfuse tracing mọi LLM call (after redaction).
- mem0 `AsyncMemory` per user_id (không dùng làm official knowledge).

## Testing & Eval

- Unit tests: no real LLM, no DB/network; fake model/tool fixtures.
- Integration tests: DB + API + adapter.
- Cross-tenant denial tests (DB + vector) — release gate.
- Product evals (`evals/`): support accuracy, isolation, moderation, injection.
- Test error paths, không chỉ happy path.

## Git Conventions

- Conventional commits: `type(scope): description`.
- Branch: `feature/description`, `fix/description`.
- PR title < 72 chars.
- Push to new branch, không trực tiếp main.

## 11 Commandments (AGENTS.md)

1. Routes có rate limiting decorators.
2. LLM operations có Langfuse tracing.
3. Async operations có proper error handling.
4. Logs structured, lowercase_underscore event names.
5. Retries dùng tenacity.
6. Console output dùng rich.
7. Cache chỉ successful responses.
8. Imports ở top of files.
9. DB operations async.
10. Endpoints có type hints + Pydantic models.
11. Code pass `make typecheck`.

## References

- `AGENTS.md` (canonical)
- [Contribution Flow](contribution-flow.md)
- [Migration Rules](../02-persistence/migration-rules.md)
