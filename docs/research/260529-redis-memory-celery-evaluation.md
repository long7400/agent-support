# Redis Memory And Celery Evaluation

## Executive Summary

Redis chạy in-memory nên rủi ro quá tải RAM là thật. Không được thiết kế Phase 2A
theo kiểu "đẩy hết event vào Redis rồi tính sau". Cách đúng là dùng Redis Streams
như transport có retention/backpressure rõ ràng, còn PostgreSQL giữ metadata và
idempotency durable.

Không nên áp dụng Celery cho chat ingress/egress lúc này. Celery hữu ích cho job
Python background như knowledge sync, indexing, report generation, scheduled
maintenance. Nhưng với Phase 2A, Redis Streams + worker mỏng đủ đơn giản hơn,
dễ trace hơn, và tránh thêm task abstraction sớm.

## Scope

Research câu hỏi:

1. Redis dùng RAM, tới ngưỡng cao sẽ quá tải. Có cách hạn chế không?
2. Celery có cần áp dụng cho Phase 2A messaging backbone không?

Repo context:

- Current baseline: FastAPI, SQLAlchemy, Alembic, PostgreSQL RLS, Redis Streams.
- ADR 0001 already says: Redis Streams, ARQ where Python-native.
- Phase 2A target: tenant platform mapping, message envelope, chat event
  persistence, Redis ingress/outbound stream, stub worker.

## Redis Memory Risk

Redis is fast because the working dataset is in RAM. If stream keys grow without
retention, memory grows with them. The failure mode is not theoretical:

- Stream length grows with event volume.
- Pending Entry Lists can grow if workers read but do not ACK.
- Client connections also consume memory.
- If `maxmemory` is not configured, Redis can keep allocating memory until the
  host is pressured.

## Redis Guardrails We Should Apply

### 1. Set `maxmemory`

Set an explicit Redis memory budget per environment. Do not leave production
unbounded.

Local example:

```text
maxmemory 256mb
```

Production value depends on instance size and persistence/replication buffers.
Leave headroom for AOF/replication/client buffers.

Design rule:

```text
redis_host_ram >= maxmemory + persistence_buffer + replication_buffer + client_buffer + os_headroom
```

Do not size Redis as if `maxmemory == process RSS`. Redis docs call out memory
that is not counted for eviction, including buffers for replicas or AOF writes.
Monitor `INFO memory.mem_not_counted_for_evict`.

### 2. Use `noeviction` for queue/stream durability

For queue-like Redis usage, silent eviction is dangerous. If Redis evicts stream
or Celery broker keys, the system can lose ordering or broker metadata.

Recommended for Phase 2A:

```text
maxmemory-policy noeviction
```

This means writes fail when Redis is full. That is good for correctness: the app
can return 503/backpressure instead of pretending the message is safely queued.

Design rule:

```text
queue/stream Redis: noeviction
cache Redis: allkeys-lru or allkeys-lfu may be OK
mixed queue+cache Redis: reject unless isolated keyspace/memory policy is reviewed
```

### 3. Trim streams

Use bounded stream retention from day one.

Patterns:

```text
XADD stream MAXLEN ~ 100000 * field value ...
XTRIM stream MAXLEN ~ 100000
XTRIM stream MINID ~ <oldest-retained-id>
```

For Phase 2A, prefer approximate `MAXLEN ~ N` on `XADD` for simple bounded
memory. Later, use time-based retention via `MINID` if we need "keep 24h of
events" semantics.

Redis 8 stream trimming also exposes reference-handling modes:

- `KEEPREF`: remove stream entries but keep references in consumer-group PEL.
- `DELREF`: remove entries and PEL references.
- `ACKED`: remove only entries already acknowledged by all consumer groups.

For Phase 2A, keep this simple:

```text
Use XADD MAXLEN ~ N first.
Do not trim below unacked messages intentionally.
Add DLQ/reclaim policy before aggressive time-based trimming.
```

Important: Redis is not the audit source. PostgreSQL `chat_events` plus later
`agent_runs`/`tool_calls` are durable incident evidence. Redis stream retention
can be short.

### 4. Track pending entries

Consumer groups can accumulate pending entries if workers crash or fail before
ACK.

Required operational checks:

- `XPENDING` per stream/group.
- Consumer idle time.
- Redelivery/claim count.
- `XINFO GROUPS` and `XINFO CONSUMERS`.
- Dead-letter stream for repeated failures.
- `XAUTOCLAIM` recovery worker later if stuck pending entries matter.

Design rule:

```text
pending_count > threshold -> pause/slow ingest
oldest_pending_idle > threshold -> reclaim or DLQ
delivery_count > retry_limit -> DLQ, then XACK original
```

### 5. ACK only after side effects

Worker must not `XACK` before the DB insert/outbound publish has succeeded.
Otherwise a crash loses the event.

For Phase 2A:

```text
read ingress -> process -> publish outbound stub -> XACK ingress
```

If processing fails:

```text
do not ACK -> retry/claim later -> after retry limit move to DLQ
```

### 6. App-level backpressure

Before publishing to Redis, the app should fail closed when Redis is unhealthy or
near limits.

Minimum checks:

- Redis command timeout.
- Stream length over threshold.
- Pending count over threshold.
- Redis used memory / maxmemory over threshold.

Behavior:

- Return `503 QUEUE_BACKPRESSURE` for internal ingest.
- Do not persist a "queued" state if publish failed.
- Keep logs redacted but include trace id and stream name.

Backpressure should use a small set of measurable gates:

```text
used_memory / maxmemory >= 0.80 -> warn
used_memory / maxmemory >= 0.90 -> reject writes
XLEN(stream) >= max_stream_length -> reject or shed low-priority messages
XPENDING(group).count >= pending_limit -> reject writes
oldest_pending_idle >= idle_limit -> trigger reclaim/DLQ path
publish latency >= timeout -> return 503
```

### 7. Keep payloads small

Redis stream event should contain envelope metadata and bounded message text.
Large attachments belong in object storage later, not Redis.

Recommended Phase 2A payload:

```json
{
  "trace_id": "uuid",
  "tenant_id": "uuid",
  "platform": "telegram",
  "channel_id": "string",
  "user_id": "string",
  "message_id": "string",
  "chat_event_id": "uuid",
  "text_preview": "bounded string"
}
```

Do not put:

- raw attachments
- full tool outputs
- long source documents
- credentials
- large LLM prompts/responses

### 8. Limit client memory

Redis client connections can consume memory through query/output buffers. Slow
clients are especially dangerous when replies pile up faster than clients can
read them.

Production config should set:

```text
timeout <seconds>
tcp-keepalive <seconds>
client-output-buffer-limit normal <hard> <soft> <seconds>
maxmemory-clients 5%
```

For app code:

- bound connection pool size
- set socket/connect/read timeouts
- never use unbounded blocking reads from many clients
- prefer a small fixed number of worker consumers per stream/group

### 9. Watch fragmentation and RSS, not only used memory

Redis may free keys internally but RSS can stay high because allocators do not
always return memory to the OS. Monitor both logical and physical memory.

Required probes:

```text
INFO memory
MEMORY STATS
MEMORY DOCTOR
```

Track:

- `used_memory`
- `used_memory_rss`
- `mem_fragmentation_ratio`
- `allocator_frag_ratio`
- `used_memory_peak`
- `mem_not_counted_for_evict`

If fragmentation stays high after large trim/delete churn, plan restart/rollover
or active defrag tuning in production. Do not assume `XTRIM` instantly lowers RSS.

### 10. Separate Redis roles later

If Redis starts handling multiple workloads, split by role:

- Redis Streams for chat transport.
- Cache Redis if needed.
- Celery/ARQ broker Redis only if adopted.

Do not mix Celery broker/result backend with chat streams on the same production
Redis instance unless memory/key policies are explicitly reviewed.

### 11. Prefer fewer streams first

Per-tenant streams sound isolated, but they multiply stream keys, consumer groups,
pending lists, and monitoring cardinality. For Phase 2A use directional shared
streams by env/platform:

```text
local:shared:ingress:telegram
local:shared:outbound:telegram
local:shared:ingress:discord
local:shared:outbound:discord
```

Put `tenant_id` in the envelope. Revisit per-tenant streams only when one tenant
has enough volume to justify isolation.

### 12. Persist idempotency in PostgreSQL, not Redis

Redis memory pressure must not break duplicate-message correctness. Store
idempotency on durable DB constraints, for example:

```text
unique(tenant_id, platform, channel_id, message_id, direction)
```

Redis stream duplicates or redeliveries then become safe: service re-reads the
existing DB row and avoids duplicate side effects.

## Celery Evaluation

### What Celery Gives

Celery is a mature distributed task queue:

- task decorators
- retries
- routing
- prefetch control
- late ACK for idempotent tasks
- time limits
- result backend
- worker memory lifecycle controls
- periodic/scheduled work

It is useful for background jobs that are not naturally ordered chat streams.

### Redis Broker Caveats

Celery with Redis has important operational caveats:

- Redis broker uses visibility timeout. If a task is not ACKed before timeout,
  it can be redelivered and executed again.
- Long visibility timeouts delay recovery of truly lost tasks.
- Celery docs warn that broker is not a database for distant-future scheduling.
- Redis eviction can remove broker keys and cause inconsistency.
- Worker prefetch can reserve too many tasks unless configured.
- Celery child processes can hold high memory until restarted; settings like
  `worker_max_tasks_per_child` and `worker_max_memory_per_child` help but add
  tuning work.

### Should We Use Celery For Phase 2A?

No.

Reasons:

1. Phase 2A needs ordered/replayable chat transport, not generic task execution.
2. Redis Streams already gives consumer groups, pending entries, ACK, and replay.
3. Celery adds another message abstraction before we have a real adapter.
4. Celery result backend can become another Redis memory surface.
5. The existing ADR says Redis Streams plus ARQ where Python-native, not Celery.

## When Celery Might Be Worth Revisiting

Revisit Celery only if we hit one of these:

- Knowledge sync needs complex retries, ETA, routing, and worker pools.
- Indexing jobs become long-running and need separate queues by cost/duration.
- We need mature operational tooling for task retries and schedules.
- ARQ is too small for required routing/retry semantics.
- We choose RabbitMQ/SQS as a dedicated broker for background jobs.

If Celery is adopted later:

- Use it for background jobs, not chat ingress/egress.
- Prefer separate broker/result backend from chat Redis.
- Make tasks idempotent.
- Configure `task_acks_late = True` only for idempotent tasks.
- Set `worker_prefetch_multiplier = 1` for long tasks.
- Set task timeouts and I/O timeouts.
- Set result expiration or avoid Redis result backend for large results.
- Configure worker memory recycling.

## Recommendation For Phase 2A

Use Redis Streams, but with hard guardrails:

```text
Redis Streams yes
Celery no
ARQ no for this slice unless we need scheduled Python jobs
PostgreSQL remains durable metadata source
```

Implementation requirements to add to the Phase 2A plan:

1. Add Redis settings:
   - `redis_url`
   - stream max length
   - stream publish timeout
   - backpressure thresholds

2. Add stream naming:
   - `local:shared:ingress:telegram`
   - `local:shared:outbound:telegram`
   - later equivalent Discord streams

3. Publish with trim:
   - `XADD ... MAXLEN ~ <limit>`

4. Worker semantics:
   - `XREADGROUP`
   - process
   - publish side effect
   - `XACK`

5. Monitoring:
   - stream length
   - pending count
   - oldest pending idle time
   - Redis memory usage
   - publish failures
   - retry/DLQ count

6. Failure behavior:
   - internal ingest returns `503 QUEUE_BACKPRESSURE` when Redis is full or too
     far behind.
   - duplicate message still returns existing persisted event / idempotent result.

7. Local failure-mode tests:
   - configure small `maxmemory`
   - force stream length over limit
   - force pending entries by not ACKing
   - verify API returns controlled `QUEUE_BACKPRESSURE`
   - verify duplicate ingest remains idempotent under redelivery

## Sources

- Redis `XTRIM`: https://redis.io/docs/latest/commands/xtrim/
- Redis key eviction and `maxmemory`: https://redis.io/docs/latest/develop/reference/eviction/
- Redis memory optimization: https://redis.io/docs/latest/operate/oss_and_stack/management/optimization/memory-optimization/
- Redis streaming guide: https://redis.io/docs/latest/develop/use-cases/streaming/
- Redis client handling and output buffers: https://redis.io/docs/latest/develop/reference/clients/
- Redis persistence and fork behavior: https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/
- Redis `XPENDING`: https://redis.io/docs/latest/commands/xpending/
- Redis `XAUTOCLAIM`: https://redis.io/docs/latest/commands/xautoclaim/
- Redis `MEMORY STATS`: https://redis.io/docs/latest/commands/memory-stats/
- Redis `MEMORY DOCTOR`: https://redis.io/docs/latest/commands/memory-doctor/
- Celery Redis broker/backend docs: https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/redis.html
- Celery optimizing docs: https://docs.celeryq.dev/en/stable/userguide/optimizing.html
- Celery task ACK/idempotency docs: https://docs.celeryq.dev/en/stable/userguide/tasks.html

## Open Questions

1. Phase 2A stream retention should be size-based only, or size plus time-based?
2. Do we want DLQ in Phase 2A, or only record retry/pending metrics first?
3. Should local `infra/docker-compose.yml` include Redis `maxmemory` and
   `maxmemory-policy noeviction` now to force failure-mode testing?
