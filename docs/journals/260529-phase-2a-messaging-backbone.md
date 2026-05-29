# Phase 2A Messaging Backbone

Date: 2026-05-29

## Summary

Implemented the local messaging backbone from normalized internal ingest through
PostgreSQL idempotency, Redis ingress, worker stub processing, and Redis outbound.
This is not the Telegram/Discord adapter runtime yet.

## Decisions

- PostgreSQL owns durable chat event idempotency.
- Redis Streams are bounded transport with `MAXLEN ~`, timeouts, connection pool
  caps, memory/stream/pending backpressure, and local `noeviction`.
- Internal ingest writes tenant-owned `chat_events` and `stream_outbox` rows with
  the app role plus tenant context, then publishes Redis after commit.
- Worker stub reloads tenant state through the app role plus tenant context and
  rejects inactive tenants before outbound publish or ACK.
- Worker stub isolates per-entry service failures within a batch and raises
  after the batch, so valid later entries are still published and ACKed.
- Internal ingest passes `AGENT_SUPPORT_REDIS_INGRESS_CONSUMER_GROUP` into
  Redis backpressure so pending-entry pressure is checked on the real group.
- Celery is deferred for the chat path. It may be useful later for coarse
  background jobs, but not for low-latency ingress/egress.
- The internal ingest route rejects request-supplied tenant ids and resolves
  trusted tenant id through `tenant_platforms`.

## Proof

- Unit tests cover message contracts, platform service behavior, message ingest,
  and Redis backpressure.
- Integration tests cover tenant/platform RLS, chat event idempotency, Redis
  publish/read/ACK, internal ingest duplicate/backpressure retry behavior,
  stream outbox RLS, worker ACK-after-publish behavior, and inactive tenant
  rejection before worker processing. Regression coverage also proves mixed
  worker batches continue after one inactive tenant and outbox `last_error`
  records the public queue error message.
- Migration rollback and upgrade are validated with Alembic.
- Secret scan is clean.

## Next

Phase 2B should implement the Telegram adapter against
`POST /internal/messages/ingest`, harden adapter auth beyond the local
`X-Internal-Token`, and add the DLQ/reclaim path for repeated worker failures.
LangGraph, RAG, and MCP remain later phases.
