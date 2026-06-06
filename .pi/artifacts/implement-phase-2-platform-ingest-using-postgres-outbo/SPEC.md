# Implement Phase 2 Platform Ingest Using Postgres Outbox

**ID:** implement-phase-2-platform-ingest-using-postgres-outbo
**Type:** epic
**Status:** planned

## Goal

Build the Phase 2 trusted platform ingest and delivery backbone: Telegram inbound webhooks now, Discord-ready adapter contracts now, durable Postgres outbox processing, idempotent outbound delivery, tenant-safe mapping, rate limiting, backpressure, auditing, and verification tests.

## Non-goals

- No real Discord production implementation in Phase 2; only contract/mock validation so Phase 7 can reuse the same normalized interfaces.
- No real LangGraph/LLM execution in the webhook request or Phase 2 worker; processing may be a deterministic stub that creates delivery work.
- No admin UI for Telegram onboarding; schema/service/API foundations are enough unless existing admin API patterns make a small endpoint cheap.
- No Kafka/NATS/Temporal introduction unless Postgres outbox cannot meet tests; ADR-003 keeps Postgres as the source of truth.
- No raw bot tokens, webhook secrets, or sensitive full message payloads in logs, metrics, traces, fixtures, or persisted audit details.

## Context

- Roadmap source: `docs/05-roadmap/phase-2-platform-ingest.md` defines P2 as platform ingest and delivery with `chat_events`, `processing_outbox`, `delivery_outbox`, per-tenant Telegram webhook, and Discord-ready adapter contract.
- Architecture source: `docs/01-architecture/adapters-and-integrations.md` requires adapters to be thin translators, forbids trusted tenant IDs in request bodies, and defines `AdapterPrincipal`, `NormalizedInboundEvent`, and `OutboundDeliveryEnvelope` shapes.
- API source: `docs/api-reference/adapter-ingest-api.md` defines `POST /v1/webhook/telegram/{tenant_id}` and `POST /v1/adapter/ingest`, with adapter principal auth separate from admin/user auth.
- Decision source: `docs/06-decisions/adr-003-graph-execution-mode.md` accepts Postgres outbox with `FOR UPDATE SKIP LOCKED`, LISTEN/NOTIFY wake-up, polling fallback, retries, DLQ, heartbeat, and stale reclaim.
- Decision source: `docs/06-decisions/adr-009-telegram-bot-strategy.md` accepts per-tenant Telegram bots with production webhook mode and secret-token verification.
- Schema reference: `docs/02-persistence/schema-reference.md` already sketches P2 tables and indexes, but implementation must reconcile naming (`heartbeat_at` vs requested `heartbeat_ts`) and add complete delivery run fields (`run_after_ts`, `worker_id`, `dead_letter`) where needed.
- Current code after P1 has tenant models/services/auth in `app/models/tenant.py`, `app/models/service_principal.py`, `app/models/audit.py`, `app/services/tenant_control_plane.py`, `app/api/v1/tenant_admin.py`, and routing in `app/api/v1/api.py`.
- Current app has no adapter/outbox implementation under `app/`; this work adds new modules rather than extending an existing P2 code path.
- Current branch is `main` and worktree is clean at creation time; no workspace branch/worktree was created by `/create`.

## Proposed Solution

Implement P2 as a set of vertical backend slices around a single durable event path.

Core decisions:

- Add a new Alembic migration for platform/messaging tables instead of modifying P1 migrations.
- Keep tenant resolution trusted: Telegram path verifies stored webhook secret and platform/channel mapping; generic adapter path verifies adapter principal and scope; request bodies cannot set trusted `tenant_id`.
- Model platform contracts as Pydantic/domain objects independent of Telegram raw update shape.
- Normalize Telegram raw updates into `NormalizedInboundEvent`, then persist a `chat_events` row plus one `processing_outbox` row in the same DB transaction.
- Use DB uniqueness for inbound idempotency: `(tenant_id, platform, external_message_id, direction)`.
- Use DB uniqueness for outbound idempotency: `(tenant_id, idempotency_key)` on `delivery_outbox`.
- Implement processing and delivery workers using `SELECT ... FOR UPDATE SKIP LOCKED`, `run_after_ts`, `worker_id`, `heartbeat_ts`, stale reclaim, exponential backoff, retries, and DLQ.
- Use a rate-limit manager in the delivery sender; Telegram has fixed sandbox buckets, Discord remains contract-ready with future route/global header parsing.
- Audit fail-closed paths and retry/DLQ events through the existing audit model/service where possible.

## Affected Files

Expected new files:

- `alembic/versions/<new>_p2_platform_ingest.py`
- `app/models/platform.py`
- `app/models/messaging.py`
- `app/schemas/adapter.py`
- `app/services/adapter_contracts.py`
- `app/services/telegram_adapter.py`
- `app/services/discord_mock_adapter.py`
- `app/services/platform_ingest.py`
- `app/services/outbox_worker.py`
- `app/services/delivery_sender.py`
- `app/services/rate_limits.py`
- `app/api/v1/platform_webhooks.py`
- `app/api/v1/adapter_ingest.py`
- `tests/adapter/test_telegram_adapter.py`
- `tests/adapter/test_adapter_ingest.py`
- `tests/adapter/test_discord_contract.py`
- `tests/outbox/test_processing_outbox.py`
- `tests/outbox/test_delivery_outbox.py`
- `tests/integration/test_platform_ingest_delivery.py`

Expected modified files:

- `app/api/v1/api.py`
- `app/core/config.py`
- `app/models/database.py` or `app/models/__init__.py` if model registration is required
- `app/worker.py` if worker entrypoint wiring is included
- `docs/02-persistence/schema-reference.md` only if implementation intentionally diverges from the reference
- `docs/api-reference/adapter-ingest-api.md` only if endpoint details are clarified during implementation

## Tasks

- [ ] Add platform and messaging persistence migration — Files: [`alembic/versions/<new>_p2_platform_ingest.py`, `app/models/platform.py`, `app/models/messaging.py`] — Verify: `uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head`
- [ ] Add adapter contract schemas and validation — Files: [`app/schemas/adapter.py`, `app/services/adapter_contracts.py`] — Verify: `uv run pytest tests/adapter/test_discord_contract.py -q`
- [ ] Add Telegram update normalization — Files: [`app/services/telegram_adapter.py`, `tests/adapter/test_telegram_adapter.py`] — Verify: `uv run pytest tests/adapter/test_telegram_adapter.py -q`
- [ ] Add trusted ingest service with idempotent transaction — Files: [`app/services/platform_ingest.py`, `app/models/messaging.py`, `app/models/platform.py`] — Verify: `uv run pytest tests/outbox/test_processing_outbox.py -q -k 'idempotency or duplicate'`
- [ ] Add Telegram webhook route with secret-token fail-closed behavior — Files: [`app/api/v1/platform_webhooks.py`, `app/api/v1/api.py`] — Verify: `uv run pytest tests/integration/test_platform_ingest_delivery.py -q -k 'webhook or secret or unknown_channel'`
- [ ] Add generic adapter ingest route with adapter principal scope checks — Files: [`app/api/v1/adapter_ingest.py`, `app/api/v1/auth.py`, `app/services/platform_ingest.py`] — Verify: `uv run pytest tests/adapter/test_adapter_ingest.py -q`
- [ ] Add processing outbox worker operations — Files: [`app/services/outbox_worker.py`, `app/worker.py`] — Verify: `uv run pytest tests/outbox/test_processing_outbox.py -q -k 'claim or reclaim or retry or dlq'`
- [ ] Add delivery sender, receipts, and outbound idempotency — Files: [`app/services/delivery_sender.py`, `app/services/telegram_adapter.py`, `app/models/messaging.py`] — Verify: `uv run pytest tests/outbox/test_delivery_outbox.py -q`
- [ ] Add rate limiting and backpressure defaults — Files: [`app/core/config.py`, `app/services/rate_limits.py`, `app/services/delivery_sender.py`, `app/services/outbox_worker.py`] — Verify: `uv run pytest tests/outbox/test_delivery_outbox.py -q -k 'rate or retry_after or duplicate'`
- [ ] Add audit/observability events for fail-closed and DLQ paths — Files: [`app/services/platform_ingest.py`, `app/services/outbox_worker.py`, `app/services/delivery_sender.py`] — Verify: `uv run pytest tests/integration/test_platform_ingest_delivery.py -q -k 'audit or dlq or invalid_token'`
- [ ] Add full P2 integration path — Files: [`tests/integration/test_platform_ingest_delivery.py`] — Verify: `uv run pytest tests/adapter tests/outbox tests/integration -q`
- [ ] Run quality gates and fix issues — Files: [`app`, `tests`, `alembic/versions`] — Verify: `uv run ruff check . && uv run pyright app`

## Implementation Details

### Persistence

Required tables:

- `tenant_platforms`: tenant platform mapping, platform, external workspace/bot/guild id, credential handle, webhook secret hash, status, timestamps, uniqueness for platform workspace mapping.
- `adapter_credentials`: adapter principal backing data, platform, tenant, credential handle/version, allowed channel patterns, status, rotation timestamp.
- `platform_channels`: tenant-owned platform channel mapping, platform, external workspace where useful, channel id, optional thread support, visibility/status.
- `chat_events`: trusted event ledger with tenant id, trace id, platform, channel/thread, direction, external message id, user hash, bounded text preview, metadata if needed, received timestamp, unique idempotency key.
- `processing_outbox`: pending graph/runtime work with status, retries, `run_after_ts`, `worker_id`, `heartbeat_ts`, `last_error`, `dead_letter`, timestamps, partial pending claim index.
- `delivery_outbox`: outbound send work with tenant id, optional/null Phase 2 `agent_run_id`, envelope JSON, idempotency key, status, retries, `run_after_ts`, `worker_id`, `heartbeat_ts`, `last_error`, `dead_letter`, timestamps, unique outbound idempotency key, partial pending claim index.
- `delivery_receipts`: delivery result linked to delivery row, platform response redacted JSON, delivered timestamp.

All tenant-owned tables should follow P1 tenant/RLS conventions where practical. If RLS is deferred for a table, document why in the migration comments and tests must still prove app-layer tenant checks.

### Config Defaults

Add these defaults in `app/core/config.py` or equivalent settings module:

- `PROCESSING_CLAIM_BATCH_SIZE=10`
- `DELIVERY_CLAIM_BATCH_SIZE=10`
- `MAX_INFLIGHT_PER_TENANT=5`
- `MAX_CONCURRENT_DELIVERIES=20`
- `PROCESSING_STALE_AFTER_SECONDS=120`
- `OUTBOX_POLL_INTERVAL_SECONDS=5`
- `RETRY_MAX_ATTEMPTS=5`
- `RETRY_BACKOFF_BASE_SECONDS=2`
- `RETRY_BACKOFF_MAX_SECONDS=300`

### Rate Limits

Telegram sender defaults:

- Per chat: 1 message/second.
- Per group: 20 messages/minute.
- Per bot global: 30 messages/second unless paid broadcast is explicitly enabled later.

Discord sender in P2:

- Contract/mock only.
- Real Phase 7 sender must parse route bucket headers and global 429 headers; do not hard-code route limits.

### Security And Audit

Audit these events at minimum:

- Webhook secret mismatch.
- Unknown channel/platform mapping.
- Adapter credential missing/invalid.
- Adapter scope mismatch.
- Disabled tenant/platform/credential.
- Retry scheduled.
- Dead letter created.
- Invalid token/403 platform response.

Never log or persist raw bot tokens, webhook secrets, adapter credential secrets, or unbounded message payloads.

## Risks

- **RLS and worker claims conflict:** outbox workers need tenant-safe access across tenants. Mitigation: use explicit service role path with audited worker operations, or claim per tenant context; document and test whichever pattern matches P1.
- **Idempotency key ambiguity across update types:** Telegram has update ids and message ids. Mitigation: choose external message id deterministically from message/update fields and test duplicate webhook retries.
- **Outbound duplicate sends after crash:** sender may crash after platform send before receipt commit. Mitigation: idempotency key, receipt checks before send, and conservative retry behavior.
- **Postgres outbox hot spots:** many workers polling can stress DB. Mitigation: partial indexes, bounded batch sizes, LISTEN/NOTIFY plus polling fallback, and per-tenant in-flight caps.
- **Telegram-specific contract leakage:** raw Telegram fields can leak into graph/runtime. Mitigation: Discord mock contract test and adapter schema tests.
- **Real platform API unavailable in CI:** use sandbox/mock sender and typed fake platform errors for tests.

## Success Criteria

- Verify: `uv run pytest tests/adapter -q`
- Verify: `uv run pytest tests/outbox -q`
- Verify: `uv run pytest tests/integration -q`
- Verify: `uv run ruff check .`
- Verify: `uv run pyright app`
- Outcome: Telegram webhook resolves a trusted tenant/platform/channel and persists one `chat_events` row plus one `processing_outbox` row.
- Outcome: Duplicate platform message returns success without duplicate processing.
- Outcome: Request body cannot provide or override trusted `tenant_id`.
- Outcome: Unknown platform/channel mapping fails closed and is audited.
- Outcome: Worker claims pending rows with `FOR UPDATE SKIP LOCKED`, processes work, retries failures, reclaims stale rows, and DLQs exhausted rows.
- Outcome: Delivery sender creates receipts only after send success and prevents duplicate outbound side effects through `idempotency_key`.
- Outcome: Webhook `secret_token` rejection works and does not leak secret material.
- Outcome: Telegram adapter and Discord mock adapter both satisfy the same platform contract.

## Open Questions

- Should worker cross-tenant claims use an operator/service DB role with audited access, or loop through tenant contexts to preserve RLS semantics? Inspect P1 RLS helpers before implementation and choose the least risky path.
- Should `agent_run_id` in `delivery_outbox` be nullable for Phase 2 stub processing, or should the stub create a placeholder run id? Prefer nullable unless Phase 3 schema already requires a run record.
- Should Telegram onboarding endpoints be included in this P2 implementation or deferred to a separate admin slice? Minimum P2 requires enough seeded/test data to verify webhook secret and channel mapping.

## Next Steps

1. Run `/plan implement-phase-2-platform-ingest-using-postgres-outbo` to decompose this epic into implementation slices with file-level sequencing.
2. Before `/ship`, create a feature branch from `main`, e.g. `git switch -c feature/p2-platform-ingest`, because the artifact was created while on `main`.
3. During planning, inspect P1 RLS/session patterns in `app/core/tenant_context.py`, `app/services/tenant_control_plane.py`, and the P1 migration before deciding the outbox worker DB-access pattern.
