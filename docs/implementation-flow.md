# Implementation Flow

## Daily Build Loop

1. Pick one task from [Task Breakdown](task-breakdown.md).
2. Read the related spec and architecture section.
3. Write or update tests first for isolation, schema, or behavior.
4. Implement the smallest vertical slice.
5. Run local validation.
6. Update docs when behavior or contracts changed.
7. Commit only related files.

Before editing code, read [Coding Rules](coding-rules.md) and [Agent Instructions](../AGENTS.md).
The default persistence stack is Pydantic schemas plus SQLAlchemy 2.x models plus Alembic migrations.

## Branch Flow

```text
main
  -> feat/m0-foundation
  -> feat/m1-tenancy
  -> feat/m2-messaging
```

Rules:

- `main` must always pass validation.
- One feature branch should map to one milestone or a small task cluster.
- Do not mix docs-only decisions with runtime refactors unless the code requires it.

## Local Development Flow

```text
uv sync --dev
docker compose -f infra/docker-compose.yml up -d --wait
uv run alembic upgrade head
uv run pytest tests/unit
AGENT_SUPPORT_RUN_INTEGRATION=1 uv run pytest tests/integration
uv run uvicorn core.api.main:app --reload
```

Expected local services:

- PostgreSQL for metadata.
- Redis for streams and background jobs.
- Qdrant for vector search.
- Optional local LLM mock for tests.

Useful probes:

```text
curl http://127.0.0.1:8000/healthz
curl http://127.0.0.1:6333/healthz
docker exec infra-redis-1 redis-cli ping
uv run alembic current
```

When a migration changes, prove rollback:

```text
uv run alembic downgrade base
uv run alembic upgrade head
```

## Implementation Order Inside a Slice

1. Schema and contracts.
2. Persistence and migrations.
3. Service logic.
4. API or adapter edge.
5. Observability.
6. Tests.
7. Docs.

Keep dependency direction clean: API calls service/domain, domain stays framework-free, persistence owns DB access.

## Testing Flow

| Test Type | When |
| --- | --- |
| Unit | Every graph node, parser, policy check, config loader. |
| Integration | DB, Redis Streams, Qdrant, MCP boundary. |
| Contract | Adapter envelope, MCP tool schemas, API responses. |
| Isolation | Every tenant-owned storage path. |
| Replay | Agent run can be replayed with mocked tool/LLM output. |
| Load | Chat ingress, RAG query, sync workers before release. |

## TurboVec Adoption Flow

TurboVec is not a default dependency of the durable RAG path. Use this flow when working on `M4-007` through `M4-009`.

1. Finish the Qdrant provider first.
2. Create `VectorSearchProvider` contract with tenant/source filters, top-k, score, citation metadata, and trace fields.
3. Implement TurboVec provider behind `RAG_ACCELERATOR=turbovec`.
4. Keep Qdrant as rebuild source and fallback path.
5. Run the same fixture corpus through Qdrant and TurboVec.
6. Compare recall, p95 latency, memory, build time, persist/load time, and answer citation quality.
7. Test selective tenant/source filters with small allowlists.
8. Test local persist/load and cold start.
9. Test fallback by corrupting or deleting the TurboVec index.
10. Update [ADR 0002](decisions/0002-turbovec-read-path-accelerator.md) with the result.

Do not enable TurboVec by default until the ADR status changes from `Proposed` to `Accepted`.

## Release Flow

1. Freeze release branch.
2. Run full validation checklist.
3. Run migration on staging.
4. Run tenant isolation suite.
5. Run smoke test with one Telegram or Discord sandbox.
6. Confirm rollback migration and previous image are available.
7. Deploy production.
8. Watch error rate, latency, token cost, and moderation actions.

## Incident Flow

1. Find `trace_id`.
2. Load `chat_events`, `agent_runs`, `tool_calls`, and `moderation_actions`.
3. Check tenant config version and enabled tools at run time.
4. Replay with mocked external calls when possible.
5. Patch policy, prompt, retrieval, or tool contract.
6. Add regression test.
7. Write a short incident note in `docs/journals/`.
