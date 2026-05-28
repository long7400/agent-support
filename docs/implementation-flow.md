# Implementation Flow

## Daily Build Loop

1. Pick one task from [Task Breakdown](task-breakdown.md).
2. Read the related spec and architecture section.
3. Write or update tests first for isolation, schema, or behavior.
4. Implement the smallest vertical slice.
5. Run local validation.
6. Update docs when behavior or contracts changed.
7. Commit only related files.

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
docker compose up -d
alembic upgrade head
pytest
python -m core.api
```

Expected local services:

- PostgreSQL for metadata.
- Redis for streams and background jobs.
- Qdrant for vector search.
- Optional local LLM mock for tests.

## Implementation Order Inside a Slice

1. Schema and contracts.
2. Persistence and migrations.
3. Service logic.
4. API or adapter edge.
5. Observability.
6. Tests.
7. Docs.

## Testing Flow

| Test Type | When |
| --- | --- |
| Unit | Every graph node, parser, policy check, config loader. |
| Integration | DB, Redis Streams, Qdrant, MCP boundary. |
| Contract | Adapter envelope, MCP tool schemas, API responses. |
| Isolation | Every tenant-owned storage path. |
| Replay | Agent run can be replayed with mocked tool/LLM output. |
| Load | Chat ingress, RAG query, sync workers before release. |

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
