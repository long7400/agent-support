# Adapters And Integrations

## Mục đích

Tài liệu này định nghĩa adapter boundaries, Telegram/Discord integration strategy, normalized event contracts, outbound delivery, external source connectors, và MCP/tool integration rules.

## Đối tượng đọc

Backend engineer, integration engineer, AI engineer, DevOps, security reviewer, và operator.

## Adapter Principle

Adapters are thin translators. They do not own tenant policy, tenant secrets, RAG, moderation decisions, or tool permission.

Adapter responsibilities:

- receive platform events,
- validate platform-specific authenticity where available,
- normalize payload,
- attach adapter credential,
- call internal ingest API,
- consume outbound delivery work,
- send platform message/action,
- ACK only after side effect succeeds,
- log trace/platform status without secrets.

## Inbound Normalized Event

Adapter sends untrusted platform data:

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

Rules:

- No trusted tenant id in request body.
- Text is bounded.
- Attachments are references, not raw large blobs.
- Adapter auth header/credential is separate from admin/user auth.

## Trusted Event After Resolution

Backend resolves tenant and creates trusted runtime event:

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

Only this trusted event enters graph execution.

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

Rules:

- Platform send happens after policy check.
- Destructive action requires moderation policy.
- Idempotency key prevents duplicate side effects.
- Delivery result links back to agent run.

## Telegram Strategy

Telegram should be first platform.

Phases:

1. Local long polling sandbox.
2. Internal ingest + outbound send.
3. Webhook production mode with Telegram secret token validation.
4. Per-tenant bot/credential strategy if required.
5. Moderation actions after policy/review gates.

Required handling:

- `getUpdates` offset or grammY runner state for long polling.
- webhook secret validation for production.
- Bot API timeout and retry limits.
- Markdown/HTML escaping and length constraints.
- Delivery receipt/idempotency for send retries.
- Platform error mapping to typed errors.

## Discord Strategy

Discord should come after Telegram path is stable.

Reasons:

- Gateway intents and message content permission can require extra setup.
- Guild/channel/thread semantics are broader.
- Rate limits and permissions need careful design.

Discord must reuse:

- normalized inbound contract,
- trusted tenant resolution,
- agent graph,
- outbound envelope shape,
- moderation policy matrix.

Discord-specific design needed:

- gateway vs interactions/webhook mode,
- message content privileged intent,
- guild/channel/thread mapping,
- bot permissions by action type,
- reconnect/resume strategy,
- slash commands/admin actions,
- Discord formatting and length constraints.

## Adapter Auth

Adapter principal should be scoped:

```text
adapter_id
platform
external_workspace_id
allowed_channel_patterns
credential_status
credential_version
last_rotated_at
```

Rules:

- Adapter credential is not admin credential.
- Credential secret is not stored in normal config JSON.
- Backend compares adapter principal scope against platform mapping.
- Logs include credential id/version, never secret.
- Production rejects local/demo adapter secrets.

## Queue And Delivery Reliability

Use one of two patterns:

### Pattern A: HTTP request path first

Good for early MVP if graph latency is acceptable.

- Ingest event.
- Run graph.
- Persist outbound.
- Adapter polls/receives delivery work.

### Pattern B: Worker/outbox path

Better for production reliability.

- Ingest persists chat event and delivery/processing outbox.
- Worker consumes.
- Graph persists run and outbound.
- Adapter sends.
- ACK only after downstream side effects.
- Reclaim/DLQ handles stuck work.

Regardless of transport:

- PostgreSQL owns durable idempotency.
- Queue is transport, not audit source.
- Retry limit sends to DLQ/review.

## Knowledge Source Integrations

First source lanes:

| Source | Recommendation |
| --- | --- |
| Admin-uploaded Markdown/FAQ | First lane. Easiest to validate. |
| URL allowlist/docs site | Early after fetch policy and domain allowlist. |
| GitBook/docs platform | Later connector once URL lane works. |
| Google Drive | Later; requires tenant credential handles and ACL mapping. |
| Raw chat | Never direct; candidate extraction + review only. |

Connector rules:

- Source approval happens before fetch/index.
- Credentials are handles.
- Fetcher stores raw snapshot/hash and redacted errors.
- Parser does not invent facts.
- Sync job records counts and failures.
- Activation happens after verification.

## Tool And MCP Integrations

Built-in tools first:

- `rag.search`
- `tenant.official_links`
- `moderation.propose_action`
- `support.escalate`

External/MCP tools later:

- `crypto.price`
- `web.search`
- analytics/reporting tools
- ticketing/CRM tools

MCP rules:

- Pin server identity/version in manifest.
- Filter tool list against manifest and tenant policy.
- No token passthrough.
- Credential handles resolved server-side.
- Remote servers run behind network egress controls.
- Side-effecting tools need idempotency and approval.

## Integration Observability

Every integration should emit:

- trace id,
- tenant id where trusted,
- platform/provider,
- action,
- latency,
- status,
- retry count,
- redacted error code,
- rate-limit state where available.

Do not emit:

- tokens,
- raw provider credentials,
- full private chat,
- full private docs,
- raw tool payloads when sensitive.

## Validation

Adapter tests:

- normalized event validation,
- no tenant id accepted from body,
- adapter credential rejects missing/wrong/scope mismatch,
- duplicate message idempotency,
- outbound ACK after send,
- send retry does not duplicate with idempotency receipt,
- platform API timeout/error mapping.

Integration tests:

- one Telegram sandbox event reaches trusted event/agent run/outbound delivery,
- disabled tenant rejected before graph/outbound,
- unknown platform mapping fails closed,
- moderation enforce action not possible without policy.

## Open Questions

- Should each tenant have its own Telegram bot or shared bot with scoped mappings?
- Which adapter deployment mode is production target: webhook, long polling worker, or both?
- What admin UX is needed to rotate adapter credentials?
- Which source connector is first after Markdown?
- Should Discord be gateway bot first or slash-command/admin interactions first?
