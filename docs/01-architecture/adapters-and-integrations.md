# Adapters And Integrations

## Mục đích

Định nghĩa adapter boundaries, Telegram/Discord strategy, normalized event contracts, outbound delivery, external source connectors, MCP/tool integration rules.

## Đối tượng đọc

Backend engineer, integration engineer, AI engineer, DevOps, security reviewer, operator.

## Adapter Principle

Adapters là thin translators. Không own tenant policy, secrets, RAG, moderation decisions, tool permission.

Adapter responsibilities: receive platform events, validate platform authenticity, normalize payload, attach adapter credential, call internal ingest API, consume outbound delivery work, send platform message/action, ACK chỉ sau side effect success, log trace/platform status không secrets.

## Inbound Normalized Event

Adapter gửi untrusted platform data:

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

Rules: no trusted tenant id in body; text bounded; attachments là references; adapter auth header tách khỏi admin/user auth.

## Trusted Event After Resolution

Backend resolve tenant → trusted runtime event:

```json
{
  "trace_id": "uuid",
  "tenant_id": "uuid",
  "input_event_id": "uuid",
  "platform": "telegram",
  "channel_id": "string",
  "thread_id": "string-or-null",
  "user_id_hash": "string",
  "message_id": "string",
  "text_preview": "bounded string",
  "received_at": "timestamp"
}
```

Chỉ trusted event này vào graph execution (qua processing_outbox).

## Outbound Delivery Envelope

```json
{
  "trace_id": "uuid",
  "tenant_id": "uuid",
  "agent_run_id": "uuid",
  "platform": "telegram",
  "channel_id": "string",
  "thread_id": "string-or-null",
  "reply_to_message_id": "string-or-null",
  "action_type": "send_message|warn|delete|ban|mute|none",
  "text": "bounded string",
  "format": "plain|markdown|html",
  "idempotency_key": "string"
}
```

Rules: platform send sau policy check; destructive action cần moderation policy; idempotency key chống duplicate side effect; delivery result link tới agent run.

## Telegram Strategy (ADR-009: Per-Tenant Bot)

**Mỗi tenant 1 bot** (tenant tạo qua BotFather, submit token). **Webhook mode** cho production. Lý do: brand isolation (@MyProjectSupportBot), Telegram rate-limit per-bot, bot ban blast radius = 1 tenant.

### Onboarding Flow
```text
1. Tenant admin login -> admin API.
2. UI/CLI hướng dẫn: chat @BotFather -> /newbot -> nhận token.
3. Admin POST /v1/admin/telegram/setup {bot_token}.
4. Backend validate token (getMe) -> store ciphertext qua KMSProvider -> handle vào tenant_platforms.
5. Backend setWebhook(url=https://api.../v1/webhook/telegram/{tenant_id}, secret_token=<random>).
6. Tenant add bot vào group/channel -> bot discover qua my_chat_member event -> admin confirm channel mapping.
```

### Fail-Closed Cases
- Token invalid → reject onboarding, audit log.
- Webhook secret mismatch → 401, audit log.
- chat_id không trong tenant_platforms mapping → drop event, audit "unknown channel".
- Bot ban detected (Telegram API error) → mark tenant_platform disabled, alert admin.

### Required Handling
- Webhook secret_token validation mọi inbound.
- Bot API timeout + retry limits.
- Markdown/HTML escaping + length constraints.
- Delivery receipt/idempotency cho send retries.
- Platform error → typed errors.

> Long-poll mode chỉ cho dev/sandbox (1 worker loop qua active tenants, asyncio). Production = webhook để giảm worker count.

## Discord Strategy (Defer Phase 7)

Discord defer Phase 7 NHƯNG adapter contract phải Discord-ready từ Phase 2. Crypto community ~40% dùng Discord → không bỏ hẳn.

Phase 2 requirement: contract (`AdapterPrincipal`, `NormalizedInboundEvent`, `OutboundDeliveryEnvelope`) verify bằng 1 paper-design Discord mock để tránh Telegram-shape leak vào contract.

Discord must reuse: normalized inbound contract, trusted tenant resolution, agent graph, outbound envelope shape, moderation policy matrix.

Discord-specific design (Phase 7): gateway vs interactions/webhook mode, message content privileged intent, guild/channel/thread mapping, bot permissions by action type, reconnect/resume, slash commands/admin actions, Discord formatting/length constraints.

Promote sớm lên Phase 5 nếu ≥30% prospects yêu cầu Discord trong pilot.

## Adapter Auth

Adapter principal scoped:
```text
adapter_id
platform
external_workspace_id
allowed_channel_patterns
credential_status
credential_version
last_rotated_at
```

Rules: adapter credential ≠ admin credential; credential secret không ở config JSON (KMS handle); backend so adapter principal scope vs platform mapping; logs có credential id/version không secret; production reject local/demo adapter secrets.

## Queue And Delivery Reliability (ADR-003: Outbox)

**Pattern chốt: Postgres outbox + polling worker.** Không sync trong request (vi phạm SLO ingest <500ms).

```text
1. Adapter POST /v1/adapter/ingest (hoặc webhook).
2. BEGIN TX
     INSERT chat_events (idempotency_key = tenant_id+platform+external_message_id)
     INSERT processing_outbox (event_id, status='pending', tenant_id, run_after_ts)
   COMMIT          # atomic, same-DB → exactly-once
3. Return 200 OK (<500ms).
4. Worker loop (asyncio):
   SELECT * FROM processing_outbox
   WHERE status='pending' AND run_after_ts <= now()
   ORDER BY id FOR UPDATE SKIP LOCKED LIMIT 10
   -> run graph (AsyncPostgresSaver checkpoint)
   -> INSERT delivery_outbox + UPDATE outbox status='done'
5. Delivery sender consume delivery_outbox -> platform send -> mark delivered.
```

Critical points:
- **Idempotency:** UNIQUE `(tenant_id, platform, external_message_id)`. Telegram retry → INSERT fails → 200 OK với existing event_id.
- **Crash recovery:** stale `processing` rows > timeout → reclaim. Worker heartbeat + worker_id.
- **Per-tenant fairness:** `ORDER BY (tenant_id, id)` hoặc partition queue per tier nếu workload không đều.
- **Retry/DLQ:** columns `retries INT`, `last_error TEXT`, `dead_letter BOOL`. Exponential backoff, N lần → dead_letter.
- **Low latency option:** worker LISTEN channel `outbox_new`, NOTIFY → poll ngay; poll fallback 5s nếu no NOTIFY.

Regardless of transport: PostgreSQL owns durable idempotency; queue/transport ≠ audit source; retry limit → DLQ/review.

Migration path: nếu >10K events/sec hoặc multi-region → swap Kafka, giữ outbox abstraction consumer interface.

## Knowledge Source Integrations

| Source | Recommendation |
| --- | --- |
| Admin-uploaded Markdown/FAQ | **First lane (Phase 4).** Easiest to validate. |
| URL allowlist/docs site | Phase 5, sau fetch policy + domain allowlist. |
| GitBook/docs platform | Later connector (reuse Markdown intermediate). |
| Google Drive | Later; requires tenant credential handles + ACL mapping. |
| Raw chat | Never direct; candidate extraction + review only. |

Connector rules: source approval trước fetch/index; credentials là handles; fetcher store raw snapshot/hash + redacted errors; parser không invent facts; sync job record counts/failures; activation sau verification.

## Tool And MCP Integrations

Built-in tools first: `rag.search`, `tenant.official_links`, `moderation.propose_action`, `support.escalate`.

External/MCP tools later: `crypto.price`, `web.search`, analytics/reporting, ticketing/CRM.

MCP rules: pin server identity/version trong manifest; filter tool list vs manifest + tenant policy; no token passthrough; credential handles resolve server-side (KMS); remote servers sau network egress controls; side-effecting tools cần idempotency + approval.

## Integration Observability

Emit: trace id, tenant id (where trusted), platform/provider, action, latency, status, retry count, redacted error code, rate-limit state.

Không emit: tokens, raw provider credentials, full private chat, full private docs, raw tool payloads khi sensitive.

## Validation

Adapter tests: normalized event validation; no tenant id from body; adapter credential reject missing/wrong/scope mismatch; duplicate message idempotency; outbound ACK after send; send retry không duplicate với idempotency receipt; platform API timeout/error mapping.

Integration tests: 1 Telegram sandbox event → trusted event/agent run/outbound delivery; disabled tenant rejected trước graph/outbound; unknown platform mapping fail closed; moderation enforce không thể without policy.

## Resolved Open Questions

- Per-tenant bot vs shared → **per-tenant bot** (ADR-009).
- Adapter deployment mode → **webhook** production, long-poll dev only.
- Source connector đầu tiên sau Markdown → **URL allowlist Phase 5**.
- Discord gateway-first vs interactions → design Phase 7 (defer).

## References

- [System Architecture](system-architecture.md)
- [Core Agent Design](core-agent-design.md)
- [Data Flow Diagrams](data-flow-diagrams.md)
- [ADR-003 Graph Execution](../06-decisions/adr-003-graph-execution-mode.md)
- [ADR-009 Telegram Bot Strategy](../06-decisions/adr-009-telegram-bot-strategy.md)
- [Adapter Ingest API](../api-reference/adapter-ingest-api.md)
