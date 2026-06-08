# Adapter Ingest API

Platform adapter → internal ingest. Auth: adapter principal (NOT admin/user). SLO ingest p95 <= 500ms excluding graph (ADR-003).

## Trust Boundary

- Adapter credential ≠ admin credential (PRD-012).
- **No trusted tenant id trong request body** — resolve qua adapter principal + platform mapping.
- Telegram webhook: `secret_token` per bot verify (ADR-009).

## Telegram Webhook

`POST /v1/webhook/telegram/{tenant_id}`

Headers: `X-Telegram-Bot-Api-Secret-Token: <secret>` (verify against `tenant_platforms.webhook_secret_hash`).

Body: raw Telegram Update object. Backend normalizes → resolve tenant → ingest.

Responses:
- `200 OK` — accepted (always fast, <500ms). Duplicate → 200 với existing event_id.
- `401` — secret_token mismatch (audit `webhook.secret_mismatch`).
- `404`/drop — unknown chat mapping (audit `unknown_channel`).

> `tenant_id` trong path là routing hint; trusted resolution vẫn qua platform mapping + secret verify.

## Generic Adapter Ingest

`POST /v1/adapter/ingest` — auth: `X-Adapter-Credential: <handle-auth>`

Body (normalized inbound, no trusted tenant id):
```json
{
  "trace_id": "uuid-or-null",
  "platform": "telegram",
  "external_workspace_id": "string",
  "channel_id": "string",
  "thread_id": "string-or-null",
  "user_id": "string",
  "message_id": "string",
  "message_type": "text|join|leave|edit|delete|reaction|unknown",
  "text": "bounded string",
  "metadata": {}
}
```

Flow:
```text
validate adapter principal scope vs platform mapping
-> resolve tenant_id
-> [TX] INSERT chat_events (idempotency UNIQUE) + processing_outbox(pending) COMMIT
-> 200 OK { "event_id": "uuid", "trace_id": "uuid" }
```

Responses:
- `200` — accepted (or idempotent duplicate).
- `401` — invalid/missing adapter credential.
- `403` — scope mismatch (channel not in `allowed_channel_patterns`).
- `404` — unknown platform mapping (fail closed + audit).

## Outbound Delivery (adapter consumes)

Adapter consume `delivery_outbox` (internal API hoặc worker push):

`GET /v1/adapter/delivery/pending` — auth: adapter principal
→ delivery envelopes (xem [adapters-and-integrations.md](../01-architecture/adapters-and-integrations.md)).

`POST /v1/adapter/delivery/{id}/ack` — auth: adapter principal
```json
{ "platform_response": {...}, "delivered": true }
```
ACK chỉ sau platform send success. Idempotency key chống duplicate send.

## Idempotency

UNIQUE `(tenant_id, platform, external_message_id, direction)`:
- Telegram retry → INSERT fails → return 200 với existing event_id, no duplicate run.
- Outbound `delivery_outbox` UNIQUE `(tenant_id, idempotency_key)`.

## Validation Tests (Phase 2)

- Normalized event validation.
- No tenant id accepted from body.
- Adapter credential reject missing/wrong/scope mismatch.
- Duplicate message idempotency.
- Outbound ACK after send.
- Send retry không duplicate.
- Platform API timeout/error mapping.
- Webhook secret_token rejection.

## Error Format

```json
{ "error_code": "ADAPTER_SCOPE_MISMATCH", "detail": "…", "trace_id": "uuid" }
```

## References

- [Adapters And Integrations](../01-architecture/adapters-and-integrations.md)
- [ADR-003 Graph Execution](../06-decisions/adr-003-graph-execution-mode.md)
- [ADR-009 Telegram Bot Strategy](../06-decisions/adr-009-telegram-bot-strategy.md)
- [Phase 2 Platform Ingest](../05-roadmap/phase-2-platform-ingest.md)
