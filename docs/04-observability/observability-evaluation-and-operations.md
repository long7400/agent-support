# Observability, Evaluation, And Operations

Logs, traces, metrics, evals, dashboards, release gates, operational controls. Metrics list: [metrics-catalog.md](metrics-catalog.md). Runbooks: [runbooks.md](runbooks.md). Eval matrix: [eval-datasets.md](eval-datasets.md).

## Đối tượng đọc

Operator, SRE/DevOps, backend engineer, AI engineer, QA, product owner, security reviewer.

## Observability Goals

Operators trả lời được:
- What happened cho trace id này?
- Tenant/config/policy/source/tool/model version nào được dùng?
- Retrieval dùng approved source + correct visibility?
- Tool run/denied/timeout/invalid?
- Tại sao moderation shadow/propose/enforce?
- Outbound delivered/retried/DLQ?
- Redaction có bảo vệ logs/traces?

## Telemetry Layers

| Layer | Purpose | Template support | Product additions |
| --- | --- | --- | --- |
| Request logs | HTTP/API | structlog + request id | tenant id, actor, trace id, route class. |
| LLM traces | Prompt/model/tool debug | Langfuse self-host (ADR-007) | redaction, tenant/run metadata, sampling. |
| Metrics | SLO + alerts | Prometheus/Grafana | graph, retrieval, tool, adapter, moderation, sync, outbox. |
| Audit records | Compliance + replay | Build new | durable internal records. |
| Eval reports | Quality regression | eval framework | product-specific datasets/metrics. |

## Trace Backend (ADR-007)

Langfuse **self-host** (Docker Compose + Postgres + Clickhouse riêng):
- 1 Langfuse project per tenant (isolation).
- Redaction callback wrapper redact secrets/PII trước flush (release gate).
- Sampling per-tenant: 100% Phase 0-3 (low volume), 10-20% production scale.
- Langfuse retention 30 days; internal `agent_runs`/`audit_events` = source of truth (nếu Langfuse down/hỏng, replay không block).
- Exit plan: nếu ops capacity thiếu, Langfuse Cloud free tier MVP + self-host khi >5 tenants/enterprise.

## Required Identifiers

Mọi runtime path mang: `trace_id`, `tenant_id`, `input_event_id`, `agent_run_id`, `platform`, `channel_id` (redacted), `user_id_hash`, `config_version`, `policy_version`, `source_version_id` (khi retrieval), `capability_version` (khi tool/sub-agent).

## Logging Rules (AGENTS.md)

structlog, event name `lowercase_with_underscores`, variables qua kwargs, `logger.exception()` cho exception.

Good:
```python
logger.info(
    "agent_run_completed",
    trace_id=trace_id, tenant_id=tenant_id, agent_run_id=agent_run_id,
    intent=intent, status="succeeded", latency_ms=latency_ms,
)
```

Avoid: f-string trong event name; raw prompts/docs/tokens/credentials/full private chat; high-cardinality secrets/full text làm metric labels; external trace id làm audit handle duy nhất.

## Trace Redaction

Trước khi gửi Langfuse/external: remove secrets/credentials; hash/omit platform user ids; summarize private source snippets; redact tool inputs/outputs by schema; sample production traces; giữ full incident evidence internal khi policy cho phép.

## Evaluation Framework

Product metrics (đầy đủ: [eval-datasets.md](eval-datasets.md)):

| Metric | Checks |
| --- | --- |
| Grounded answer | Response supported by retrieved approved source. |
| Citation quality | Citation points to correct source/version/section. |
| Refusal correctness | Empty/stale/low-confidence → refuse/escalate. |
| Tenant isolation | No response uses another tenant's data. |
| Tool denial | Disabled/missing/invalid tool fail closed. |
| Moderation safety | Scam/toxic classified without destructive default. |
| Prompt injection resistance | User/source/tool text không override policy. |
| Platform formatting | Telegram output fits formatting/length rules. |
| Tone & helpfulness | Concise, useful cho member. |

## Release Gates

Trước production release: lint/type/test pass; migrations up/down reviewed; secret scan clean; tenant isolation tests; vector isolation tests; adapter sandbox smoke; eval suite threshold; trace redaction tests; backup/restore tested; rollback plan documented; production secrets ngoài git; alert routes configured.

CI source of truth = Makefile/workflows; mirror product gates.

## Dashboards

API health/latency; agent graph runs by tenant/intent/status; LLM cost/latency by tenant/model; retrieval quality + empty/stale rates; tool denials/timeouts/errors; adapter delivery + outbox health; knowledge sync status; moderation decisions + review queue; tenant isolation/security checks.

## Alerting

API 5xx > threshold; p95 support latency > SLO; moderation fast path > SLO; LLM timeout/fallback spike; vector empty retrieval spike for active sources; outbox pending/DLQ > threshold; tool timeout spike; secret scan failure CI; cross-tenant isolation test failure; production local/default secret detected.

## Backup And Retention

Backup: PostgreSQL primary; Qdrant snapshot; object storage; KMS policies/metadata. Single VPS (ADR-008) → nightly off-site (B2/Storage Box).

Retention: theo Decision 13 (chat 90d, runs 180d, audit 2y, moderation 1y, traces 30d, outbox 7d). Chi tiết: [../02-persistence/persistence-strategy.md](../02-persistence/persistence-strategy.md).

## Resolved Open Questions

- Trace backend → Langfuse self-host (ADR-007).
- Eval thresholds → [eval-datasets.md](eval-datasets.md).
- Backup RTO/RPO → single VPS nightly (RPO ~24h MVP); migrate managed khi enterprise SLA (ADR-008).
- Audit retention → 2y (Decision 13).
- Tenant id metric labels → allowed at MVP scale (10-100 tenants); review cardinality khi scale.

## References

- [Metrics Catalog](metrics-catalog.md)
- [Runbooks](runbooks.md)
- [Eval Datasets](eval-datasets.md)
- [ADR-007 Trace Backend](../06-decisions/adr-007-trace-backend.md)
