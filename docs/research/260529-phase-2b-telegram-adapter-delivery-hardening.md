# Research Report: Phase 2B Telegram Adapter And Delivery Hardening

Conducted: 2026-05-29

## Executive Summary

Sau Phase 2A, bước đúng nhất là **Phase 2B: Telegram adapter + adapter auth + Redis DLQ/reclaim**. Đây là lát cắt nhỏ nhất tạo được runtime thật từ Telegram sandbox vào `/internal/messages/ingest`, đồng thời đóng lỗ hổng vận hành còn lại của Streams: pending entries bị kẹt và retry vô hạn.

Không nên làm Discord trước. Discord cần gateway intents và message content có thể là privileged intent trong nhiều guild, nên chi phí setup/sandbox cao hơn Telegram. Không nên nhảy sang LangGraph ngay vì delivery path chưa có bot runtime thật và chưa có reclaim/DLQ.

## Repo Context

- Phase 2A đã có normalized internal ingest, `tenant_platforms`, `chat_events`, `stream_outbox`, Redis Streams bounded publisher/consumer, backpressure, worker stub.
- `adapters/telegram-bot/` và `adapters/discord-bot/` hiện mới là placeholder.
- `docs/coding-rules.md` yêu cầu adapters mỏng, tenant id từ trusted context, route handlers mỏng, background jobs verify tenant status, external calls có timeout/typed errors/logging.
- `docs/technical-plan.md` đã defer Telegram adapter runtime, Discord adapter runtime, DLQ/reclaim, và production adapter-to-control-plane auth sang Phase 2B.

## Research Methodology

- Source type: official docs first.
- Key terms: Telegram Bot API webhook secret token, grammY deployment long polling webhook runner, Discord message content intent, Redis Streams pending autoclaim DLQ.
- Recency requirement: current official docs as of 2026-05-29.

## Key Findings

### 1. Telegram Is Best First Adapter

Telegram supports both long polling and webhook models through the Bot API. For local sandbox, long polling via grammY is simpler because it does not require a public HTTPS endpoint. Production can move to webhook once deploy URL, TLS, secret validation, and operational routing are ready.

Telegram Bot API also supports a webhook `secret_token`, delivered back as `X-Telegram-Bot-Api-Secret-Token`. This is useful later for validating Telegram-to-adapter traffic, but it does not replace adapter-to-control-plane auth.

Design implication:

- Phase 2B should use long polling for local sandbox.
- Keep webhook as documented production mode, not Phase 2B blocker.
- The adapter sends only normalized internal envelopes to FastAPI.

### 2. Discord Should Be Deferred

Discord bots need gateway intents. For most guild message content access, the Message Content intent is privileged and can add approval/setup friction. That makes Discord a worse first sandbox target than Telegram.

Design implication:

- Keep Discord contract-compatible.
- Do not implement Discord runtime in the main Phase 2B path.
- Revisit after Telegram path proves adapter auth, ingest, delivery, and DLQ/reclaim.

### 3. Redis Reclaim/DLQ Is Required Before Real Traffic

Phase 2A correctly ACKs only after side effects. The remaining operational gap is what happens when an ingress entry remains in the Pending Entries List after worker crash/failure.

Redis Streams provides:

- `XPENDING` to inspect pending counts, idle time, and delivery metadata.
- `XAUTOCLAIM` to claim messages idle longer than a threshold.
- `XACK` to acknowledge original entries after successful processing or after moving to DLQ.

Design implication:

- Add a reclaim worker path before broader traffic.
- Move entries above retry limit to `{env}:{tenant_id}:dlq:{platform}`.
- Preserve `trace_id`, original stream id, failure class, and retry count in DLQ.
- Do not treat Redis as audit source; PostgreSQL remains durable evidence.

### 4. Adapter Auth Must Split From Admin Auth

Current local `X-Internal-Token` is acceptable as a placeholder but too coarse for production-shaped adapters. Adapter auth should be a separate trust model from admin API auth.

Minimum clean design:

- Adapter presents a platform connection credential scoped to tenant/platform/workspace.
- FastAPI resolves tenant from trusted credential plus `tenant_platforms`, not request body.
- Secret material is not stored in `tenant_platforms.config`.
- Logs contain tenant id, platform, trace id, redacted credential id; never token value.

For Phase 2B, a conservative middle step is acceptable:

- Introduce an adapter auth dependency and tests.
- Keep credential storage local/dev-safe if real secret manager is not available.
- Document production secret-manager boundary as deferred.

## Recommended Architecture

```text
Telegram sandbox adapter
        |
        | normalized event + adapter credential
        v
FastAPI internal ingest
        |
        +--> adapter auth dependency
        +--> tenant_platforms lookup
        +--> chat_events idempotency
        +--> stream_outbox retry state
        +--> Redis ingress stream
                    |
                    v
              worker stub
                    |
                    +--> outbound stream
                    |
                    +--> reclaim/DLQ worker for stale pending entries
```

## Backend Design Rules For Phase 2B

### Boundaries

- `adapters/telegram-bot/`: TypeScript/Node platform translation only.
- `core/api/`: FastAPI dependencies, request DTOs, response DTOs, thin routes.
- `core/services/`: ingest/auth orchestration and typed service errors.
- `core/persistence/`: SQLAlchemy repositories and migrations only.
- `core/streams/`: Redis transport helpers, reclaim, DLQ publish/read helpers.
- `core/workers/`: deterministic worker entrypoints.

### Clean Code Requirements

- No Telegram payload shape should leak into `core/services`.
- No adapter reads tenant secrets directly from DB.
- No `tenant_id` from adapter request body.
- No route-level raw SQL.
- Every external HTTP call from adapter has timeout and typed error handling.
- Every stream operation has timeout/backpressure handling.
- Every DLQ/reclaim decision is traceable with redacted structured logs.
- Tests prove behavior at boundaries, not internal implementation trivia.

### TDD Requirements

Write tests before implementation for:

- Telegram update normalization to internal event.
- Adapter auth accepts valid scoped credential and rejects missing/wrong credential.
- Tenant/platform lookup cannot be bypassed by request body tenant id.
- Stale pending Redis entry is reclaimed with `XAUTOCLAIM`.
- Entry exceeding retry limit is copied to DLQ and ACKed from original stream.
- DLQ payload preserves `trace_id`, `tenant_id`, platform, original stream id, and failure summary.
- Integration path: sandbox normalized Telegram message reaches `chat_events` and ingress stream.

## Evaluated Options

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| Telegram adapter first | Fastest real sandbox, lower permissions friction, proves existing ingest | Still needs token/auth handling | Recommended |
| Discord adapter first | Important product target | Message content privileged intent friction, more setup before value | Defer |
| LangGraph next | Starts agent behavior | Delivery/auth/DLQ not hardened, likely rewrites later | Defer |
| DLQ/reclaim before adapter | Hardens transport early | No platform-visible proof | Do together with Telegram |

## Phase 2B Scope

In scope:

- Telegram sandbox adapter runtime.
- Adapter auth dependency and tests.
- Platform connection/admin API adjustments only where needed for trusted adapter credentials.
- Redis reclaim/DLQ workflow.
- Docs/runbook for local Telegram sandbox.

Out of scope:

- Discord runtime.
- LangGraph/LLM response generation.
- RAG/Qdrant indexing.
- MCP tool execution.
- Real production secret manager integration.
- Celery for chat ingress/egress.

## Validation Gates

Required before Phase 2B can be called done:

```bash
uv run ruff check .
uv run mypy .
uv run pytest tests/unit
docker compose -f infra/docker-compose.yml up -d --wait
uv run alembic upgrade head
AGENT_SUPPORT_RUN_INTEGRATION=1 uv run pytest tests/integration
uv run python scripts/check_secret_scan.py
```

If migrations change:

```bash
uv run alembic downgrade base
uv run alembic upgrade head
```

Adapter package should also have its own lint/type/test commands once package metadata exists.

## References

- grammY deployment types: https://grammy.dev/guide/deployment-types.html
- grammY runner plugin: https://grammy.dev/plugins/runner
- Telegram Bot API `getUpdates`: https://core.telegram.org/bots/api#getupdates
- Telegram Bot API `setWebhook`: https://core.telegram.org/bots/api#setwebhook
- Discord Gateway intents: https://discord.com/developers/docs/events/gateway#gateway-intents
- Discord Message Content intent: https://discord.com/developers/docs/events/gateway#message-content-intent
- discord.js intents guide: https://discordjs.guide/popular-topics/intents.html
- Redis `XPENDING`: https://redis.io/docs/latest/commands/xpending/
- Redis `XAUTOCLAIM`: https://redis.io/docs/latest/commands/xautoclaim/
- Redis `XREADGROUP`: https://redis.io/docs/latest/commands/xreadgroup/

## Next Steps

1. Create Phase 2B TDD plan.
2. Keep Telegram + DLQ/reclaim as one bounded phase cluster.
3. Start implementation only after plan approval.
4. After Phase 2B, choose between minimal LangGraph responder and Discord adapter based on whether the product needs visible support answers or multi-platform coverage first.

## Unresolved Questions

1. Should adapter credentials be stored in the existing DB temporarily with encrypted/redacted value, or should Phase 2B only define the dependency and use env/local config until a secret manager exists?
2. Should Telegram outbound send be included in Phase 2B, or should the adapter stop at inbound sandbox plus outbound-stream observation?
