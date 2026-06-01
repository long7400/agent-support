# Metrics Catalog

Full Prometheus metric list. Labels include `tenant_id` at MVP scale (10-100 tenants); review cardinality khi scale. Naming: `agent_support_<area>_<metric>`.

## API

| Metric | Type | Labels |
| --- | --- | --- |
| `api_requests_total` | counter | route, method, status |
| `api_request_duration_seconds` | histogram | route, method |
| `api_auth_failures_total` | counter | reason |
| `api_rate_limit_denials_total` | counter | route, tenant_id |
| `api_validation_errors_total` | counter | route |

## Agent Runtime

| Metric | Type | Labels |
| --- | --- | --- |
| `graph_runs_total` | counter | tenant_id, status, intent |
| `graph_node_duration_seconds` | histogram | node_name |
| `graph_run_failures_total` | counter | tenant_id, node_name |
| `graph_replays_total` | counter | tenant_id |
| `graph_checkpoint_failures_total` | counter | — |
| `graph_policy_refusals_total` | counter | tenant_id, reason |

## LLM

| Metric | Type | Labels |
| --- | --- | --- |
| `llm_call_duration_seconds` | histogram | provider, model |
| `llm_tokens_total` | counter | tenant_id, model, direction |
| `llm_cost_usd_total` | counter | tenant_id, model |
| `llm_retries_total` | counter | provider, model |
| `llm_timeouts_total` | counter | provider, model |
| `llm_structured_output_failures_total` | counter | model |

## Retrieval (RAG / Qdrant)

| Metric | Type | Labels |
| --- | --- | --- |
| `rag_query_duration_seconds` | histogram | tenant_id |
| `rag_empty_retrieval_total` | counter | tenant_id |
| `rag_low_confidence_total` | counter | tenant_id |
| `rag_stale_source_refusal_total` | counter | tenant_id |
| `rag_cross_tenant_denial_total` | counter | — (should stay 0 in prod; test health) |
| `rag_visibility_denial_total` | counter | tenant_id |

## Tools / Capabilities

| Metric | Type | Labels |
| --- | --- | --- |
| `tool_attempts_total` | counter | capability, status |
| `tool_denials_total` | counter | capability, reason |
| `tool_timeouts_total` | counter | capability |
| `tool_input_invalid_total` | counter | capability |
| `tool_output_invalid_total` | counter | capability |
| `tool_missing_credential_total` | counter | capability |
| `tool_idempotency_conflicts_total` | counter | capability |

## Adapters & Outbox (ADR-003)

| Metric | Type | Labels |
| --- | --- | --- |
| `adapter_ingest_total` | counter | platform, status |
| `adapter_ingest_duration_seconds` | histogram | platform |
| `outbound_delivery_total` | counter | platform, status |
| `delivery_retries_total` | counter | platform |
| `processing_outbox_pending` | gauge | — |
| `delivery_outbox_pending` | gauge | — |
| `outbox_dead_letter_total` | counter | kind |
| `platform_rate_limit_responses_total` | counter | platform |
| `outbox_claim_latency_seconds` | histogram | — (poll→claim) |

## Knowledge Sync

| Metric | Type | Labels |
| --- | --- | --- |
| `sync_jobs_total` | counter | tenant_id, status |
| `sync_fetch_total` / `sync_parse_total` / `sync_chunk_total` / `sync_embed_total` / `sync_upsert_total` | counter | status |
| `sync_partial_failures_total` | counter | tenant_id |
| `sync_activation_duration_seconds` | histogram | — |
| `source_tombstone_verifications_total` | counter | status |

## Moderation

| Metric | Type | Labels |
| --- | --- | --- |
| `moderation_decisions_total` | counter | tenant_id, mode, category |
| `moderation_destructive_actions_total` | counter | tenant_id, action_type |
| `moderation_false_positive_total` / `moderation_false_negative_total` | counter | tenant_id |
| `review_queue_age_seconds` | gauge | tenant_id |

## SLO-Tied Metrics

| SLO | Metric | Target |
| --- | --- | --- |
| Support answer p95 | `graph_runs` end-to-end | <= 4s before send |
| Moderation fast path p95 | rule/classifier decision | <= 1s |
| Adapter ingest p95 | `adapter_ingest_duration_seconds` | <= 500ms (excl graph) |
| Tool timeout | `tool_timeouts_total` | <= configured per tool |
| Sync status update | `sync_activation_duration_seconds` | visible < 5s |
| Availability | up/health probes | 99.5% monthly |

## Cardinality Guidance

- `tenant_id` label OK ở 10-100 tenants. Khi >100 → drop tenant_id từ histogram, giữ ở counter, hoặc dùng exemplars.
- Never label với raw text, secrets, message ids, full channel names.

## References

- [Observability + Eval + Ops](observability-evaluation-and-operations.md)
- [Runbooks](runbooks.md)
- Product Requirements SLO: [../00-foundation/product-requirements.md](../00-foundation/product-requirements.md)
