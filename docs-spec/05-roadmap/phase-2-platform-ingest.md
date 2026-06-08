# Phase 2: Platform Ingest And Delivery

**Goal:** create trusted runtime event path với durable outbox (ADR-003) + per-tenant Telegram bot (ADR-009).

## Scope

- Adapter credential/principal model + tenant platform mapping.
- Normalized inbound event endpoint + webhook (per-tenant Telegram bot).
- `chat_events` + idempotency.
- `processing_outbox` + `delivery_outbox` + worker (SKIP LOCKED).
- Telegram sandbox adapter.
- **Adapter contract Discord-ready** (paper-design mock test).

## Deliverables

### Messaging Schema (ADR-003)
- `chat_events` (UNIQUE idempotency), `processing_outbox`, `delivery_outbox`, `delivery_receipts`, `tenant_platforms`, `adapter_credentials`, `platform_channels`.
- Outbox claim indexes (partial WHERE status='pending').

### Ingest Path
```text
webhook /v1/webhook/telegram/{tenant_id} (secret_token verify)
-> adapter normalize (no trusted tenant id in body)
-> validate adapter principal -> resolve tenant/platform mapping
-> [TX] INSERT chat_events + processing_outbox -> COMMIT
-> 200 OK (<500ms)
```
- Idempotency: duplicate → INSERT fails → 200 với existing event_id.
- Unknown mapping → drop + audit "unknown channel" (fail closed).

### Worker (ADR-003)
```text
loop:
  SELECT ... FROM processing_outbox
  WHERE status='pending' AND run_after_ts <= now()
  ORDER BY id FOR UPDATE SKIP LOCKED LIMIT 10
  -> (Phase 2: stub processing) -> INSERT delivery_outbox -> mark done
```
- LISTEN/NOTIFY wake-up + polling fallback.
- Stale `processing` reclaim (heartbeat + worker_id).
- Retry/DLQ (retries, last_error, dead_letter).
- Backpressure settings required before real load: claim batch size, max concurrent deliveries, per-platform send timeout, retry backoff ceiling, and in-flight cap per tenant. Defaults must fit the `WORKER_*` Compose CPU/memory caps.

### Delivery Sender
```text
consume delivery_outbox -> Telegram send -> delivery_receipts -> mark delivered
```
- ACK chỉ sau platform send success. Idempotency key chống duplicate.

### Per-Tenant Telegram Bot (ADR-009)
- Onboarding: BotFather token → KMS encrypt → `tenant_platforms` + credential handle.
- `setWebhook(secret_token)`. Verify secret mọi inbound.
- `my_chat_member` discover → channel mapping confirm.
- Fail-closed: invalid token, secret mismatch, unknown chat, bot ban.

### Discord-Ready Contract
- `AdapterPrincipal`, `NormalizedInboundEvent`, `OutboundDeliveryEnvelope` không Telegram-shape leak.
- 1 mock Discord adapter verify contract (no real Discord impl).

## Exit Criteria

- [ ] Telegram message resolves tenant + persists trusted event.
- [ ] Duplicate platform message idempotent.
- [ ] Adapter cannot supply trusted tenant id.
- [ ] Outbound delivery idempotent.
- [ ] Unknown mapping fails closed.
- [ ] Worker processes events from outbox (SKIP LOCKED).
- [ ] Adapter contract validated with Telegram + Discord paper-design mock.
- [ ] Webhook secret_token rejection works.

## Validation

```bash
pytest tests/adapter        # normalized event, no tenant id from body, scope mismatch
pytest tests/outbox         # idempotency, claim, reclaim, DLQ
pytest tests/integration    # 1 Telegram sandbox event -> trusted event -> delivery
```

## Risks

| Risk | Mitigation |
| --- | --- |
| Telegram webhook retry → duplicate | Idempotency UNIQUE constraint. |
| Worker crash mid-processing | Stale reclaim + (Phase 3) checkpoint resume. |
| Telegram-shape leaks into contract | Discord mock test gate. |
| secret_token bypass | 401 + audit; reject before tenant resolution. |
| Worker overwhelms DB/platform API | Bound claim batch + delivery concurrency; alert on queue age before increasing container caps. |

## References

- [ADR-003 Graph Execution](../06-decisions/adr-003-graph-execution-mode.md)
- [ADR-009 Telegram Bot Strategy](../06-decisions/adr-009-telegram-bot-strategy.md)
- [Adapters And Integrations](../01-architecture/adapters-and-integrations.md)
- [Adapter Ingest API](../api-reference/adapter-ingest-api.md)
