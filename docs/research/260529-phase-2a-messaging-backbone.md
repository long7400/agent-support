# Phase 2A Messaging Backbone Research Summary

## Executive Summary

Sau control-plane, bước hợp lý nhất là Phase 2A: messaging backbone trước khi làm
LangGraph, RAG, MCP, hoặc bot adapter đầy đủ. Mục tiêu là chứng minh một đường
runtime thật: tenant platform mapping -> normalized inbound message -> persisted
chat event -> Redis ingress stream -> worker stub -> Redis outbound stream.

Không nên nhảy thẳng vào agent engine. Nếu chưa có ingress/egress, graph chỉ là
logic trong phòng lab và khó test idempotency, trace, tenant boundary.

## Current Repo Context

- Stack hiện tại: Python 3.14, FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic,
  PostgreSQL RLS, Redis/Qdrant local infra.
- Control-plane đã có tenant CRUD, plugin toggles, audit log, admin token
  placeholder, trace id, and consistent error envelope.
- `chat_events` exists and is RLS-protected, but it is inbound-only and does not
  yet have runtime repository/service/API ingestion.
- `tenant_platforms` is documented as required but deferred from Phase 1.
- `adapters/telegram-bot` and `adapters/discord-bot` are placeholders.

## External Research Notes

- Redis Streams are append-only logs with consumer groups, pending-entry lists,
  at-least-once delivery, `XACK`, and recovery through claim/autoclaim flows.
  This fits chat ingress/egress better than pub/sub because replay and recovery
  matter.
- Redis docs highlight multiple independent consumer groups on one stream, which
  leaves room for future workers such as agent runtime, analytics, moderation,
  and audit processors.
- FastAPI dependencies with `yield` match the repo's current DB session pattern:
  acquire boundary resource, yield, clean up reliably.
- SQLAlchemy docs recommend explicit constraints/index constructs for composite
  or named constraints. Use this for `(tenant_id, platform, external ids)` and
  idempotency keys.
- grammY supports both long polling and webhooks. For local sandbox, long polling
  is simpler; production can move to webhooks after the internal envelope and
  stream contract are stable.

References:

- Redis streaming with redis-py: https://redis.io/docs/latest/develop/use-cases/streaming/redis-py/
- Redis `XREADGROUP`: https://redis.io/docs/latest/commands/xreadgroup/
- FastAPI dependencies with yield: https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/
- SQLAlchemy constraints/index guidance: https://docs.sqlalchemy.org/en/20/core/metadata.html
- grammY deployment types: https://grammy.dev/guide/deployment-types.html

## Recommended Scope

Build Phase 2A as a backend slice, not a bot slice.

### In Scope

1. Add `tenant_platforms`.
   - `tenant_id`
   - `platform`: `telegram` or `discord`
   - external workspace/chat identifiers
   - status
   - config JSON without raw secrets
   - timestamps
   - unique constraints for platform identity
   - RLS and app-role isolation tests

2. Define message contracts.
   - Internal inbound envelope
   - Internal outbound envelope
   - Platform enum
   - Message direction enum
   - Validation for required tenant/platform/user/channel/message fields

3. Add chat event repository/service.
   - Idempotent insert based on tenant/platform/channel/message identity
   - Trace id preserved
   - Tenant/platform mapping verified before persistence
   - No tenant id accepted blindly from untrusted adapter body

4. Add Redis stream boundary.
   - Thin stream publisher
   - Thin consumer helper
   - Stream naming from `docs/coding-rules.md`
   - Consumer group setup
   - Ack after DB side effects
   - Tests for publish/read/ack using local Redis

5. Add internal ingest API or service entrypoint.
   - Accept normalized adapter event
   - Resolve trusted tenant through registered `tenant_platforms`
   - Persist `chat_events`
   - Publish ingress stream
   - Return accepted response with trace id

6. Add stub worker.
   - Reads ingress stream
   - Emits deterministic outbound stub or echo response
   - Proves trace id survives through stream path
   - No LangGraph yet

### Out of Scope

- Real Telegram bot runtime beyond a local proof adapter.
- Discord adapter runtime.
- LangGraph agent execution.
- LLM calls.
- RAG/Qdrant knowledge sync.
- MCP tools.
- OAuth/OIDC admin auth.
- Secret storage for bot tokens.

## Architecture Sketch

```text
Telegram/Discord adapter later
        |
        v
normalized internal event
        |
        v
FastAPI internal ingest route or service
        |
        +--> tenant_platforms lookup
        +--> chat_events idempotent insert
        +--> Redis ingress stream
                    |
                    v
              stub worker
                    |
                    v
              Redis outbound stream
```

## Main Trade-Offs

### Option A: Start with real Telegram bot

Pros:
- Faster visible demo.
- Proves platform translation early.

Cons:
- Forces bot-token handling, long-poll/webhook decisions, and platform edge cases
  before the internal contract is stable.
- Higher chance of mixing adapter concerns into core.

Verdict: too early.

### Option B: Build internal messaging backbone first

Pros:
- Creates stable contract for both Telegram and Discord.
- Lets tests cover tenant mapping, idempotency, Redis, and DB behavior.
- Enables LangGraph later without redesigning ingress.

Cons:
- Less flashy in demo.
- Needs a small stub worker to feel end-to-end.

Verdict: recommended.

### Option C: Jump to LangGraph agent engine

Pros:
- Core product logic starts sooner.

Cons:
- No production-shaped input/output path.
- Replay and trace design will likely be rewritten when messaging arrives.

Verdict: reject for now.

## Proposed Deliverables

1. `tenant_platforms` migration/model/repository/service.
2. `core/api/schemas/messages.py` or equivalent internal message contracts.
3. `core/services/messages.py` for ingest orchestration.
4. `core/persistence/repositories/chat_events.py`.
5. `core/streams/` with Redis publisher/consumer helpers.
6. Internal ingest route, likely under `/internal/messages` or `/internal/ingest`.
7. `core/workers/` stub ingress-to-outbound worker.
8. Integration tests for Postgres RLS, idempotency, Redis publish/read/ack.
9. Docs update for stream names, envelope shape, and local validation commands.

## Acceptance Criteria

- Duplicate platform message produces one persisted `chat_events` row.
- Tenant A cannot register/read/write tenant B platform or chat rows.
- Ingest does not trust `tenant_id` from raw adapter payload.
- Redis message includes `tenant_id`, `trace_id`, platform, channel, user, and
  message id.
- Worker only ACKs after producing the expected side effect.
- Stub outbound event preserves the original trace id.
- Full local validation remains green:
  - `uv run ruff check .`
  - `uv run mypy .`
  - `uv run pytest tests/unit`
  - `docker compose -f infra/docker-compose.yml up -d --wait`
  - `uv run alembic downgrade base && uv run alembic upgrade head`
  - `AGENT_SUPPORT_RUN_INTEGRATION=1 uv run pytest tests/integration`
  - `uv run python scripts/check_secret_scan.py`

## Recommended Build Order

1. Contracts first: platform/message schemas and stream naming.
2. Persistence: `tenant_platforms`, `chat_events` idempotency, migration/RLS.
3. Service layer: platform resolution and ingest orchestration.
4. Redis boundary: publisher/consumer group helpers.
5. API edge: internal ingest endpoint with trace/error envelope.
6. Worker stub: ingress to outbound.
7. Tests and docs.

## Risks

- Overbuilding a generic event framework. Keep stream helpers tiny.
- Treating Redis as source of truth. PostgreSQL remains durable metadata source.
- Storing bot secrets in `tenant_platforms`. Do not do this in Phase 2A.
- ACKing before DB/outbound side effects. That loses messages.
- Mixing adapter-specific Telegram/Discord payloads into core message contracts.

## Open Questions

1. Should internal ingest be HTTP-only first, or service-only with an HTTP route
   added when adapter work begins?
2. Should outbound messages be persisted now, or should Phase 2A only prove Redis
   outbound events and leave durable outbound persistence for agent runtime?
3. Do we want a single shared stream with tenant in envelope, or per-environment
   directional streams such as `local:shared:ingress:telegram`?
