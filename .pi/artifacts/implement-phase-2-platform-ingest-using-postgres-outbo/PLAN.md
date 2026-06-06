# Phase 2 Platform Ingest Implementation Plan

**Work ID:** implement-phase-2-platform-ingest-using-postgres-outbo
**Spec:** `.pi/artifacts/implement-phase-2-platform-ingest-using-postgres-outbo/SPEC.md`
**Goal:** Build Telegram ingest, generic adapter ingest, Postgres processing/delivery outboxes, rate-limited delivery, and Discord-ready adapter contracts without running graph/LLM work in webhook requests.
**Discovery Level:** 3 - cross-cutting data model, auth/RLS, external platform contracts, worker runtime, and migrations.
**Context Budget:** Large epic. Execute in 6 waves; each wave should fit one `/ship` subtask or one focused implementation session.

## Institutional Findings

- Current stack is Python 3.13, FastAPI, SQLAlchemy 2.0 async, Alembic, PostgreSQL, LangGraph skeleton.
- P1 is already implemented on `main` with RLS-first tenant control plane in `app/core/tenant_context.py`, `app/services/tenant_control_plane.py`, `app/api/v1/auth.py`, and migration `alembic/versions/7b3d2e8f9a10_p1_tenant_control_plane.py`.
- P1 tenant context uses transaction-scoped `SET LOCAL app.current_tenant` via `with_tenant_context(session, tenant_id)`. P2 tenant-owned tables should use the same forced RLS policy pattern.
- Existing tests are mostly guardrail/source tests, not DB integration tests. P2 should add source/behavior tests first, then DB tests if local test fixtures support it.
- Git history contains old `feat: add phase 2a messaging backbone` and `feat(telegram): add phase 2b adapter delivery hardening` commits in a previous code layout (`core/`, `adapters/`). Current rebuild docs say do not port old code. Use those commits only as cautionary prior art, not as implementation source.
- Current `app/worker.py` is a Phase 0 idle worker shell intended to be replaced by Phase 2 SKIP LOCKED outbox work.
- No current `app` files implement adapters or outboxes; P2 adds new modules.
- Worktree was clean during planning; current branch is `main`. Create a feature branch before implementation.

## Must-Haves

### Observable Truths

1. Telegram webhook rejects invalid `X-Telegram-Bot-Api-Secret-Token` before trusted ingest and audits the rejection.
2. Telegram webhook accepts a valid update, resolves tenant/platform/channel mapping from trusted DB state, and persists exactly one trusted `chat_events` row plus one `processing_outbox` row.
3. Duplicate inbound platform messages return success and do not enqueue duplicate processing.
4. Generic adapter ingest accepts only normalized events and adapter principal auth; request body cannot provide or override trusted `tenant_id`.
5. Processing worker claims pending rows using `FOR UPDATE SKIP LOCKED`, handles retry/backoff, reclaims stale rows, and marks exhausted rows as DLQ/dead-letter.
6. Delivery sender claims delivery rows, respects rate-limit/backpressure state, sends via platform adapter abstraction, writes receipt after success, and avoids duplicate outbound side effects.
7. Telegram adapter and Discord mock adapter both use the same `NormalizedInboundEvent` and `OutboundDeliveryEnvelope` contracts.
8. Sensitive values are never logged or stored in audit metadata: bot tokens, webhook secrets, adapter credential secrets, and unbounded raw message text.

### Required Artifacts

| Truth | Required Artifacts |
| --- | --- |
| Valid/invalid Telegram webhook behavior | `app/api/v1/platform_webhooks.py`, `app/services/telegram_adapter.py`, `app/services/platform_ingest.py`, `tests/integration/test_platform_ingest_delivery.py` |
| Trusted tenant/channel resolution | `tenant_platforms`, `platform_channels`, service queries, RLS-aware transactions |
| Inbound idempotency | `chat_events` unique constraint, ingest service duplicate handling, tests |
| Generic adapter principal path | `app/schemas/adapter.py`, `app/api/v1/adapter_ingest.py`, adapter credential model/service, auth dependency |
| SKIP LOCKED processing | `app/services/outbox_worker.py`, migration claim index, retry/DLQ tests |
| Delivery sender and receipts | `app/services/delivery_sender.py`, `app/services/rate_limits.py`, `delivery_outbox`, `delivery_receipts`, tests |
| Contract reuse | `app/services/adapter_contracts.py`, `app/services/discord_mock_adapter.py`, contract tests |
| Secret safety | audit helper, redaction rules, source tests for forbidden logging patterns |

### Key Links And Risks

| From | To | Via | Risk | Mitigation |
| --- | --- | --- | --- | --- |
| Webhook | Ingest service | normalized Telegram update | trusting path/body tenant id | Treat path tenant as routing hint only; resolve from secret/platform mapping; test body tenant ignored. |
| Generic adapter API | DB mapping | adapter credential | adapter credential becomes admin credential | Separate adapter auth dependency and schema; no reuse of JWT/admin dependencies except session plumbing. |
| Worker | RLS tables | cross-tenant claim | RLS blocks worker or bypass leaks data | Claim work outside tenant-specific business reads only when necessary, then process under `with_tenant_context`; audit worker actions. |
| Outbound retry | Platform API | delivery sender | duplicate side effects after crash | Check existing receipt/idempotency before send; persist receipt and delivered status atomically after success. |
| Rate limiter | Delivery queue | run_after_ts | busy loop on exhausted buckets | If bucket unavailable, update `run_after_ts` and release row. |
| Telegram raw update | Runtime contract | metadata/text | Telegram-specific fields leak | Keep raw payload out of runtime; bounded metadata; Discord mock test catches assumptions. |

## Dependency Graph

- **Wave 0: Workspace and baseline checks** - needs spec only; creates safe branch/checkpoint.
- **Wave 1: Schema and models** - needs P1 migration/model patterns; creates DB tables, RLS, ORM models.
- **Wave 2: Contracts and normalization** - can run after or parallel with Wave 1 for pure schemas; creates adapter interfaces, Telegram normalizer, Discord mock.
- **Wave 3: Ingest APIs and idempotency** - needs Waves 1-2; creates Telegram webhook and generic adapter ingest.
- **Wave 4: Outbox processing and delivery** - needs Waves 1-3; creates worker claim/retry/DLQ, delivery sender, rate limiting.
- **Wave 5: Audit, integration, quality gates** - needs Waves 3-4; validates full path and hardens observability/secret safety.

## Tasks

### Task 0: Prepare Safe Workspace And Baseline

- **Goal:** Start implementation from a clean, inspectable state without modifying `main` directly.
- **Scope:** git workspace only; no code changes.
- **Steps:**
  1. Run `git status --porcelain` and confirm clean tree.
  2. Create branch `feature/p2-platform-ingest` from current `main`.
  3. Run baseline tests that currently exist to identify unrelated failures.
- **Files:** none.
- **Verification:** `git branch --show-current && uv run pytest tests/test_p0_infra.py tests/test_p1_tenant_control_plane.py tests/test_p1_tenant_isolation.py -q`
- **Expected Result:** branch is `feature/p2-platform-ingest`; baseline P0/P1 tests pass or failures are documented before P2 edits.
- **Safety Notes:** Do not run destructive git commands. Do not revert user changes if the tree is unexpectedly dirty; stop and ask.

### Task 1: Add Platform/Messaging Schema And ORM Models

- **Goal:** Create durable P2 tables with tenant ownership, idempotency, claim indexes, retry fields, and RLS conventions.
- **Scope:** `alembic/versions/<new>_p2_platform_ingest.py`, `app/models/platform.py`, `app/models/messaging.py`, `app/models/tenant.py` if relationships are added, `app/models/database.py` or import registry if needed, `tests/outbox/test_p2_schema_guardrails.py`.
- **Steps:**
  1. Read P1 migration and model patterns before writing migration.
  2. Add migration revising `7b3d2e8f9a10` with tables: `tenant_platforms`, `adapter_credentials`, `platform_channels`, `chat_events`, `processing_outbox`, `delivery_outbox`, `delivery_receipts`.
  3. Add check constraints for status/platform/direction/action where practical.
  4. Add unique constraints: inbound `(tenant_id, platform, external_message_id, direction)`, outbound `(tenant_id, idempotency_key)`.
  5. Add partial claim indexes where `status = 'pending'` and include `run_after_ts`.
  6. Add `run_after_ts`, `worker_id`, `heartbeat_ts`, `retries`, `last_error`, and `dead_letter` to both outbox tables.
  7. Enable and force RLS on tenant-owned P2 tables using the P1 `current_setting('app.current_tenant', true)` pattern.
  8. Add SQLAlchemy ORM models with typed enums/constants but keep table names aligned with docs.
  9. Add guardrail tests checking migration strings for forced RLS, unique constraints, partial indexes, and SKIP LOCKED claim prerequisites.
- **Verification:** `uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head && uv run pytest tests/outbox/test_p2_schema_guardrails.py -q`
- **Expected Result:** migration upgrades/downgrades cleanly; tests prove required tables/indexes/RLS fields exist.
- **Safety Notes:** Do not edit existing P1 migration. If SQLite-only tests cannot execute Alembic, keep migration guardrail tests source-based and document DB integration gap.

### Task 2: Add Adapter Contract Schemas And Contract Validators

- **Goal:** Establish Telegram/Discord-neutral contracts before any platform-specific route depends on them.
- **Scope:** `app/schemas/adapter.py`, `app/services/adapter_contracts.py`, `app/services/discord_mock_adapter.py`, `tests/adapter/test_discord_contract.py`.
- **Steps:**
  1. Define `Platform`, `MessageDirection`, `MessageType`, and outbound action/format constants or enums.
  2. Define `AdapterPrincipal` with adapter id, platform, external workspace id, allowed channel patterns, credential status/version, tenant id only after trusted lookup when appropriate.
  3. Define `NormalizedInboundEvent` with no trusted tenant id field.
  4. Define `OutboundDeliveryEnvelope` with trusted tenant id, platform/channel/thread, action type, bounded text, and idempotency key.
  5. Add validation for bounded text, allowed platform values, message id presence, and no extra trusted body fields if Pydantic config supports it.
  6. Implement Discord mock adapter that produces/consumes the same contracts without referencing Telegram field names.
  7. Add tests that fail if `tenant_id` appears in inbound request schema or if contract code depends on Telegram-only keys.
- **Verification:** `uv run pytest tests/adapter/test_discord_contract.py -q`
- **Expected Result:** generic contracts validate and Discord mock proves no Telegram-shaped assumptions.
- **Safety Notes:** Keep contracts small and stable. Do not include raw platform payloads except bounded/redacted metadata.

### Task 3: Add Telegram Normalization

- **Goal:** Convert raw Telegram Update objects into normalized inbound events with deterministic external IDs and bounded text.
- **Scope:** `app/services/telegram_adapter.py`, `tests/adapter/test_telegram_adapter.py`.
- **Steps:**
  1. Implement extraction for `message`, `edited_message`, `channel_post`, `edited_channel_post`, and `my_chat_member` enough for P2 mapping/onboarding tests.
  2. Map Telegram chat id to `channel_id`, `message_thread_id` to `thread_id`, sender id to `user_id`, and message id/update id to deterministic `message_id`/external id.
  3. Bound text preview according to contract; store attachments/media as references in metadata, not binary.
  4. Return a `NormalizedInboundEvent` with `platform='telegram'` and `external_workspace_id` set to bot id/workspace value passed from trusted platform mapping or route context.
  5. Add tests for normal message, edited message, service/member update, missing text, large text truncation, and no trusted tenant id from body.
- **Verification:** `uv run pytest tests/adapter/test_telegram_adapter.py -q`
- **Expected Result:** Telegram raw payloads normalize consistently and safely.
- **Safety Notes:** Never parse bot token from webhook path/body. Keep raw Telegram update out of persisted runtime event unless redacted/bounded.

### Task 4: Implement Trusted Ingest Service And Idempotent Transaction

- **Goal:** Centralize tenant/platform/channel resolution and atomic `chat_events + processing_outbox` creation for both Telegram webhook and generic adapter ingest.
- **Scope:** `app/services/platform_ingest.py`, `app/models/platform.py`, `app/models/messaging.py`, `app/core/tenant_context.py` only if a helper is needed, `tests/outbox/test_processing_outbox.py`.
- **Steps:**
  1. Add service errors for secret mismatch, unknown mapping, disabled platform, invalid adapter credential, scope mismatch, duplicate accepted, and tenant disabled.
  2. Add trusted lookup helpers for `tenant_platforms`, `platform_channels`, and `adapter_credentials` under tenant context once tenant is known.
  3. For Telegram webhook, verify secret hash against `tenant_platforms.webhook_secret_hash` using constant-time comparison against hashed input.
  4. Resolve channel mapping and status; fail closed on unknown/disabled/scope mismatch.
  5. Insert `chat_events` and `processing_outbox` in one transaction under `with_tenant_context`.
  6. On inbound uniqueness conflict, fetch existing event id and return accepted duplicate without inserting a second outbox row.
  7. Add optional `NOTIFY outbox_new` after new processing row if practical; otherwise leave a clearly documented polling fallback.
  8. Add tests for new event, duplicate event, unknown mapping, disabled platform, and body tenant id ignored.
- **Verification:** `uv run pytest tests/outbox/test_processing_outbox.py -q -k 'idempotency or duplicate or unknown or disabled'`
- **Expected Result:** one central ingest service handles idempotency and trusted resolution for all inbound paths.
- **Safety Notes:** Do not expose raw SQL errors in API responses. Do not log secrets or full message text in service errors.

### Task 5: Add Telegram Webhook API Route

- **Goal:** Expose `POST /v1/webhook/telegram/{tenant_id}` with fast ACK, secret-token verification, normalization, fail-closed behavior, and audit.
- **Scope:** `app/api/v1/platform_webhooks.py`, `app/api/v1/api.py`, `app/services/platform_ingest.py`, `tests/integration/test_platform_ingest_delivery.py`.
- **Steps:**
  1. Add router and include it in `app/api/v1/api.py` with path matching docs.
  2. Read header `X-Telegram-Bot-Api-Secret-Token` and reject missing/wrong token.
  3. Treat path `tenant_id` as route hint only; service must still verify secret and mapping.
  4. Normalize update through Telegram adapter and pass to ingest service.
  5. Return `200` for accepted new event and accepted duplicate.
  6. Return/audit `401` for secret mismatch; fail closed on unknown mapping as docs require, choosing either `404` or drop+audit consistently with tests.
  7. Add integration tests with seeded tenant/platform/channel rows.
- **Verification:** `uv run pytest tests/integration/test_platform_ingest_delivery.py -q -k 'webhook or secret or unknown_channel'`
- **Expected Result:** Telegram webhook path is wired and enforces trust boundary.
- **Safety Notes:** Endpoint must not call graph/LLM or platform send. Keep response body minimal and non-sensitive.

### Task 6: Add Generic Adapter Ingest API And Adapter Principal Auth

- **Goal:** Expose `POST /v1/adapter/ingest` for normalized platform adapters with scoped adapter principal auth separate from admin/user auth.
- **Scope:** `app/api/v1/adapter_ingest.py`, `app/api/v1/api.py`, `app/api/v1/auth.py` or `app/services/adapter_contracts.py`, `app/services/platform_ingest.py`, `tests/adapter/test_adapter_ingest.py`.
- **Steps:**
  1. Add an adapter credential auth dependency using a dedicated header such as `X-Adapter-Credential` as specified in docs.
  2. Resolve adapter principal from `adapter_credentials`; reject missing/invalid/disabled credentials.
  3. Validate normalized inbound schema with extra fields forbidden, especially `tenant_id`.
  4. Check principal platform/workspace/channel scope before ingest.
  5. Reuse central ingest service transaction/idempotency path.
  6. Add tests for missing credential, wrong credential, disabled credential, scope mismatch, tenant id in body, accepted event, and duplicate accepted.
- **Verification:** `uv run pytest tests/adapter/test_adapter_ingest.py -q`
- **Expected Result:** generic adapter ingest works and does not rely on Telegram webhook details.
- **Safety Notes:** Do not reuse human JWT auth or service-principal tenant admin scopes for adapter auth. Adapter credential secrets must be hashed/handles only.

### Task 7: Implement Processing Outbox Worker Operations

- **Goal:** Replace idle worker internals with reusable processing outbox operations that claim, heartbeat, process stub work, retry, reclaim, and DLQ.
- **Scope:** `app/services/outbox_worker.py`, `app/worker.py`, `app/core/config.py`, `tests/outbox/test_processing_outbox.py`.
- **Steps:**
  1. Add settings: `PROCESSING_CLAIM_BATCH_SIZE`, `PROCESSING_STALE_AFTER_SECONDS`, `OUTBOX_POLL_INTERVAL_SECONDS`, `RETRY_MAX_ATTEMPTS`, `RETRY_BACKOFF_BASE_SECONDS`, `RETRY_BACKOFF_MAX_SECONDS`, `MAX_INFLIGHT_PER_TENANT`.
  2. Implement claim query using `SELECT ... FOR UPDATE SKIP LOCKED`, `status='pending'`, and `run_after_ts <= now()` ordered by tenant-aware/fair order where practical.
  3. Mark claimed rows `processing` with `worker_id` and `heartbeat_ts`.
  4. Implement stale reclaim for rows stuck in `processing` past configured timeout.
  5. Implement Phase 2 stub processing: create a `delivery_outbox` row with deterministic idempotency key, then mark processing row `done`.
  6. Implement retry scheduling with exponential backoff and DLQ/dead-letter after max attempts.
  7. Wire `app/worker.py` to run processing role when `WORKER_ROLE=processing` or default runtime role includes processing.
  8. Add source/behavior tests for SKIP LOCKED SQL string, claim status changes, backoff, stale reclaim, DLQ, and stub delivery insertion.
- **Verification:** `uv run pytest tests/outbox/test_processing_outbox.py -q -k 'claim or reclaim or retry or dlq or stub'`
- **Expected Result:** processing outbox can be exercised without platform APIs and has crash-recovery primitives.
- **Safety Notes:** If RLS blocks cross-tenant claim, implement claim by selecting candidate ids via a safe service-role path and process each row under its tenant context; document this in code and tests.

### Task 8: Implement Delivery Sender, Receipts, And Rate Limiting

- **Goal:** Send delivery outbox rows through platform abstraction with idempotency, receipts, typed error handling, and rate-limit-aware scheduling.
- **Scope:** `app/services/delivery_sender.py`, `app/services/rate_limits.py`, `app/services/telegram_adapter.py`, `app/services/adapter_contracts.py`, `app/core/config.py`, `tests/outbox/test_delivery_outbox.py`.
- **Steps:**
  1. Add settings: `DELIVERY_CLAIM_BATCH_SIZE`, `MAX_CONCURRENT_DELIVERIES`, Telegram bucket defaults.
  2. Implement in-memory rate-limit bucket manager suitable for tests; persist scheduling via `delivery_outbox.run_after_ts` when bucket unavailable or 429 occurs.
  3. Implement delivery claim query with `FOR UPDATE SKIP LOCKED` and pending/run-after filters.
  4. Before send, check for existing successful receipt or delivered status for the delivery/idempotency key.
  5. Implement sandbox/mock Telegram sender that returns typed success/error results without real credentials.
  6. On success, insert `delivery_receipts` and mark delivery `delivered` in the same transaction.
  7. On 429, timeout, or 5xx, schedule retry/backoff; on invalid token/403, audit and mark failed/dead-letter or disable platform per service decision.
  8. Add tests for success receipt, duplicate send prevention, 429 retry_after, timeout retry, invalid token handling, and max retry DLQ.
- **Verification:** `uv run pytest tests/outbox/test_delivery_outbox.py -q`
- **Expected Result:** delivery processing is idempotent, rate-limit-aware, and platform-abstracted.
- **Safety Notes:** Do not call real Telegram API in tests. Redact platform responses before storing receipts.

### Task 9: Add Audit And Observability Guardrails

- **Goal:** Ensure fail-closed paths and worker failures are traceable without leaking secrets.
- **Scope:** `app/services/platform_ingest.py`, `app/services/outbox_worker.py`, `app/services/delivery_sender.py`, `app/models/audit.py`, `tests/integration/test_platform_ingest_delivery.py`, optional `tests/adapter/test_secret_redaction.py`.
- **Steps:**
  1. Add a small audit helper for P2 actions using existing `AuditEvent` model and `ActorContext` style.
  2. Emit audit events for secret mismatch, unknown channel, scope mismatch, disabled platform/credential, retry scheduled, DLQ, and invalid token.
  3. Bind log context with `trace_id`, trusted `tenant_id` after resolution, platform, status, retry count, and latency.
  4. Add tests/source checks ensuring webhook secret and credential secret values are not included in logs/audit metadata.
  5. Confirm all errors returned to clients use non-sensitive messages.
- **Verification:** `uv run pytest tests/integration/test_platform_ingest_delivery.py -q -k 'audit or redaction or dlq or invalid_token'`
- **Expected Result:** operators can debug P2 failures while sensitive platform secrets remain hidden.
- **Safety Notes:** Avoid storing raw inbound bodies in audit records. Store bounded previews or hashes only.

### Task 10: Full Integration Path And Quality Gates

- **Goal:** Prove end-to-end Phase 2 behavior and keep codebase quality gates green.
- **Scope:** all P2 app/test files plus optional docs updates if implementation clarified contracts.
- **Steps:**
  1. Add/complete integration test: seeded tenant + Telegram platform + channel + secret -> webhook update -> `chat_events` -> `processing_outbox` -> worker stub -> `delivery_outbox` -> sender -> `delivery_receipts`.
  2. Add integration test for duplicate webhook retry producing no duplicate processing/delivery.
  3. Add integration test for unknown channel fail-closed and audit.
  4. Run grouped tests and fix failures.
  5. Run ruff and pyright; fix style/type issues.
  6. If schema or endpoint behavior differs from docs, update docs in the same final task and mention divergence.
- **Verification:** `uv run pytest tests/adapter -q && uv run pytest tests/outbox -q && uv run pytest tests/integration -q && uv run ruff check . && uv run pyright app`
- **Expected Result:** P2 success criteria pass as a cohesive system.
- **Safety Notes:** If local database services are unavailable, report which DB-backed verifications could not run and keep source/contract tests passing.

## File Change Map

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
- `tests/adapter/test_secret_redaction.py` optional
- `tests/outbox/test_p2_schema_guardrails.py`
- `tests/outbox/test_processing_outbox.py`
- `tests/outbox/test_delivery_outbox.py`
- `tests/integration/test_platform_ingest_delivery.py`

Expected modified files:

- `app/api/v1/api.py`
- `app/api/v1/auth.py`
- `app/core/config.py`
- `app/worker.py`
- `app/models/tenant.py` if relationships are useful
- `app/models/database.py` or model import registry if needed
- `docs/02-persistence/schema-reference.md` only for intentional schema clarifications
- `docs/api-reference/adapter-ingest-api.md` only for intentional endpoint clarifications

## Plan Checkpoints

- **Checkpoint A after Task 1:** DB schema and ORM are in place; migration upgrade/downgrade works.
- **Checkpoint B after Task 3:** Adapter contract and Telegram normalization tests pass without DB.
- **Checkpoint C after Task 6:** Both inbound APIs use one idempotent ingest service.
- **Checkpoint D after Task 8:** Processing and delivery outbox tests pass without real platform APIs.
- **Checkpoint E after Task 10:** Full P2 verification commands pass or blocked commands are documented with cause.

## Constitutional Compliance

- Stage only explicit files if committing; never use broad staging shortcuts.
- Keep verification hooks enabled.
- Never rewrite remote history.
- Avoid destructive git cleanup or reset operations.
- Do not install new dependencies without a specific approval/checkpoint; current scope should be achievable with existing FastAPI/SQLAlchemy stack.
- Do not call real Telegram or Discord APIs in CI tests.

Constitutional compliance: PASS

## Next Command

`/ship implement-phase-2-platform-ingest-using-postgres-outbo`
