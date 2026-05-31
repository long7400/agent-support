# Observability, Evaluation, And Operations

## Mục đích

Tài liệu này định nghĩa logs, traces, metrics, evals, dashboards, runbooks, release gates, incident handling, và operational controls cho Agent Support.

## Đối tượng đọc

Operator, SRE/DevOps, backend engineer, AI engineer, QA, product owner, và security reviewer.

## Observability Goals

Operators must answer:

- What happened for this trace id?
- Which tenant/config/policy/source/tool/model version was used?
- Did retrieval use approved source and correct visibility?
- Did a tool run, get denied, timeout, or return invalid output?
- Why did moderation shadow/propose/enforce?
- Was an outbound message delivered, retried, or DLQ'd?
- Did redaction protect logs/traces?

## Telemetry Layers

| Layer | Purpose | Template support | Product additions |
| --- | --- | --- | --- |
| Request logs | HTTP/API behavior | structlog + request id | tenant id, actor, trace id, route class. |
| LLM traces | Prompt/model/tool debug | Langfuse callback | redaction, tenant/run metadata, sampling. |
| Metrics | SLO and alerts | Prometheus/Grafana | graph, retrieval, tool, adapter, moderation, sync metrics. |
| Audit records | Compliance and replay | Build new | durable internal records. |
| Eval reports | Quality regression | eval framework | product-specific datasets and metrics. |

## Required Identifiers

Every runtime path should carry:

- `trace_id`
- `tenant_id`
- `input_event_id`
- `agent_run_id`
- `platform`
- `channel_id` or redacted equivalent
- `user_id_hash` where possible
- `config_version`
- `policy_version`
- `source_version_id` when retrieval occurs
- `capability_version` when tool/sub-agent runs

## Metrics

### API

- request count by route/status
- request latency by route
- auth failures
- rate limit denials
- validation errors

### Agent Runtime

- graph run count by tenant/status/intent
- graph node latency
- graph failure rate
- replay count
- checkpoint failure count
- policy refusal/escalation count

### LLM

- model call latency
- token usage and estimated cost by tenant/model
- retry/fallback count
- timeout count
- structured output validation failure

### Retrieval

- vector query latency
- empty retrieval rate
- low confidence rate
- stale source refusal rate
- cross-tenant denial test health
- source visibility denial count

### Tools

- tool attempts by capability/status
- denied tool count by reason
- timeout rate
- invalid input/output count
- missing credential count
- side-effect idempotency conflict count

### Adapters And Queues

- adapter ingest count/failures
- outbound delivery success/failure
- retry count
- queue lag/pending count if using queue/streams
- DLQ count
- platform rate-limit responses

### Knowledge Sync

- sync jobs by status
- fetch/parse/chunk/embed/upsert counts
- partial failure count
- activation latency
- source delete/tombstone verification

### Moderation

- shadow/propose/enforce counts
- category distribution
- false positive/negative review outcomes
- destructive action count
- review queue age.

## Logging Rules

Use structured logs.

Good:

```python
logger.info(
    "agent_run_completed",
    trace_id=trace_id,
    tenant_id=tenant_id,
    agent_run_id=agent_run_id,
    intent=intent,
    status="succeeded",
    latency_ms=latency_ms,
)
```

Avoid:

- interpolating sensitive values into event names,
- logging raw prompts, raw docs, tokens, credentials, full private chat,
- using high-cardinality secrets or full text as metric labels,
- relying on external trace id as the only audit handle.

## Trace Redaction

Before sending traces to Langfuse or any external backend:

- remove secrets/credentials,
- hash or omit platform user ids,
- summarize private source snippets,
- redact tool inputs/outputs by schema,
- sample production traces,
- keep full incident evidence in internal storage when allowed by policy.

## Evaluation Framework

Template evals should be extended with product metrics:

| Metric | What it checks |
| --- | --- |
| Grounded answer | Response supported by retrieved approved source. |
| Citation quality | Citation points to correct source/version/section. |
| Refusal correctness | Empty/stale/low-confidence retrieval refuses or escalates. |
| Tenant isolation | No response uses another tenant's data. |
| Tool denial | Disabled/missing/invalid tool requests fail closed. |
| Moderation safety | Scam/toxic examples classified without destructive default. |
| Prompt injection resistance | User/source/tool text cannot override policy. |
| Platform formatting | Telegram/Discord output fits formatting and length rules. |
| Tone and helpfulness | Answer is concise and useful for community member. |

Datasets:

- official FAQ questions,
- tokenomics/roadmap/listing facts,
- stale docs cases,
- missing knowledge cases,
- scam/phishing/toxic messages,
- prompt injection in user messages and source docs,
- disabled tool attempts,
- cross-tenant leakage fixtures,
- multilingual community messages,
- Telegram formatting edge cases.

## Runbooks

### Bad Answer Investigation

1. Get trace id, platform message id, or agent run id.
2. Load tenant config/policy/model/source/tool versions.
3. Inspect retrieval context and citation pack.
4. Inspect model call summary and policy check result.
5. Inspect tool calls and denials.
6. Check outbound delivery and platform formatting.
7. Add regression fixture.
8. Patch source, prompt, policy, retrieval, or tool contract.

### Suspected Tenant Leak

1. Freeze affected tenant/run if needed.
2. Identify storage path: SQL, vector, cache, queue, trace, eval.
3. Verify tenant filters and role/policy used.
4. Run cross-tenant denial tests.
5. Rotate credentials if secret exposure possible.
6. Remove/redact leaked traces or reports if policy requires.
7. Add regression and security review finding.

### Queue/Delivery Backlog

1. Check queue lag/pending/DLQ.
2. Check adapter platform errors/rate limits.
3. Check worker health and last processed id.
4. Reclaim stale pending work if safe.
5. Confirm idempotency before replay.
6. Scale workers or throttle ingest.

### Knowledge Sync Failure

1. Inspect sync job status and redacted error.
2. Check source credentials/allowlist/fetch result.
3. Check parse/chunk/embed/upsert counts.
4. Verify partial source version is not active.
5. Retry after fix or mark source stale/tombstoned.

## Release Gates

Before production release:

- lint/type/test gates pass,
- migrations upgrade/downgrade or forward-only rollback reviewed,
- secret scan clean,
- tenant isolation tests pass,
- vector isolation tests pass,
- adapter sandbox smoke passes,
- eval suite passes threshold,
- trace redaction tests pass,
- backup/restore tested,
- rollback plan documented,
- production secrets configured outside git,
- alert routes configured.

Template command names may evolve. Keep the CI source of truth in Makefile/workflows and mirror product gates there.

## Dashboards

Recommended dashboards:

- API health and latency.
- Agent graph runs by tenant/intent/status.
- LLM cost and latency by tenant/model.
- Retrieval quality and empty/stale rates.
- Tool denials/timeouts/errors.
- Adapter delivery and queue health.
- Knowledge sync status.
- Moderation decisions and review queue.
- Tenant isolation/security checks.

## Alerting

Initial alerts:

- API 5xx rate above threshold.
- p95 support latency above SLO.
- moderation fast path above SLO.
- LLM timeout/fallback spike.
- vector empty retrieval spike for active sources.
- queue pending/DLQ above threshold.
- tool timeout spike.
- secret scan failure in CI.
- cross-tenant isolation test failure.
- production local/default secret detected.

## Backup And Retention

Backup:

- PostgreSQL primary database.
- Vector backend if external.
- object storage snapshots if used.
- secret manager policies and metadata.

Retention:

- chat events: tenant policy and legal needs,
- agent runs: enough for incident/debug/eval,
- audit: longer compliance window,
- traces: shorter and redacted,
- eval datasets: redacted/minimized,
- source snapshots: per-source retention.

## Open Questions

- What pass thresholds should product evals use before tenant rollout?
- Which traces can leave production environment?
- What backup/restore RTO/RPO is required?
- How long should audit records be retained?
- Which metrics are allowed to include tenant id labels at production scale?
