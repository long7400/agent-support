# Runbooks

Operational runbooks. Mỗi runbook: trigger → steps → resolution → follow-up.

## 1. Bad Answer Investigation

**Trigger:** member/admin báo câu trả lời sai, hallucinate, hoặc thiếu citation.

```text
1. Lấy trace_id / platform message_id / agent_run_id.
2. Load tenant config/policy/model/source/tool versions @ run time.
3. Inspect retrieval context + citation pack (Qdrant hits, source_version).
4. Inspect model_calls summary + policy_check result.
5. Inspect tool_calls + denials.
6. Check delivery_outbox + platform formatting.
7. Classify root cause: retrieval | prompt | model | policy | tool | adapter | data.
```

**Resolution:** patch source / prompt / policy / retrieval / tool contract.
**Follow-up:** add regression fixture vào eval dataset.

## 2. Suspected Tenant Leak (P0 Security)

**Trigger:** dấu hiệu tenant A thấy data tenant B; cross-tenant denial test fail; alert.

```text
1. Freeze affected tenant/run nếu cần (set tenant suspended).
2. Identify storage path: SQL | Qdrant | cache | outbox | trace | eval.
3. Verify tenant filters + role/policy used (app_user không BYPASSRLS?).
4. Run cross-tenant denial tests (DB + vector).
5. Rotate credentials nếu secret exposure possible (KMS DEK rotate).
6. Remove/redact leaked traces/reports nếu policy yêu cầu.
7. Add regression + security review finding.
```

**Resolution:** fix missing RLS policy / missing vector tenant filter / SET LOCAL outside tx.
**Follow-up:** post-mortem; audit operator access during incident.

## 3. Queue / Delivery Backlog (Outbox)

**Trigger:** `processing_outbox_pending` / `delivery_outbox_pending` gauge spike; DLQ count up.

```text
1. Check outbox pending/DLQ counts (SQL).
2. Check adapter platform errors / rate limits (Telegram).
3. Check worker health + last processed id + heartbeat.
4. Reclaim stale 'processing' rows > timeout (safe — idempotent).
5. Confirm idempotency before replay.
6. Scale workers (more containers) hoặc throttle ingest.
```

**Resolution:** restart/scale worker; clear poison message → dead_letter; fix platform credential.
**Follow-up:** review retry/backoff config; check per-tenant fairness ordering.

## 4. Knowledge Sync Failure

**Trigger:** sync job status=failed; member báo missing knowledge.

```text
1. Inspect knowledge_sync_jobs status + redacted error.
2. Check source credentials/allowlist/fetch result.
3. Check parse/chunk/embed/upsert counts.
4. Verify partial source_version KHÔNG active (active=false).
5. Retry after fix hoặc mark source stale/tombstoned.
```

**Resolution:** re-upload/re-sync; fix parser; reactivate verified version.
**Follow-up:** ensure activation gate worked (no partial visibility).

## 5. Telegram Bot Down / Banned (Per-Tenant, ADR-009)

**Trigger:** Telegram API errors cho 1 tenant; bot không reply.

```text
1. Check tenant_platforms status + last webhook receipt.
2. Test getMe với credential handle (KMS decrypt).
3. Check setWebhook status (Telegram getWebhookInfo).
4. Nếu bot banned -> mark tenant_platform disabled + alert admin.
5. Blast radius = 1 tenant (per-tenant bot isolation).
```

**Resolution:** tenant re-create bot via BotFather → re-submit token → re-register webhook.
**Follow-up:** review abuse pattern gây ban.

## 6. LLM Provider Degradation

**Trigger:** `llm_timeouts_total` / `llm_retries_total` spike; support p95 > SLO.

```text
1. Check provider status + latency metrics.
2. Verify circular fallback đang chạy (template LLM service).
3. Check model budget exhaustion per tenant.
4. Consider safe_fallback (refuse/escalate) nếu sustained.
```

**Resolution:** failover provider; raise temporary budget; degrade gracefully.
**Follow-up:** review cost/budget config.

## 7. Tenant Deletion (GDPR <30d)

**Trigger:** tenant request deletion.

```text
1. Set tenant status=deleting (stop new ingest, adapter reject tenant_inactive).
2. Drain in-flight outbox -> finish hoặc DLQ.
3. Hard delete: chat_events, agent_runs/steps, model_calls, moderation_*,
   knowledge_chunks, Qdrant collection, Langfuse project, credential handles (KMS revoke).
4. Audit tenant_deleted event (kept).
5. Mark tenant row deleted (giữ FK trong audit).
6. Complete < 30 days.
```

**Resolution:** verify Qdrant collection gone + KMS DEK revoked.
**Follow-up:** confirm backups rotated out within retention.

## 8. KMS Unavailable

**Trigger:** GCP KMS decrypt fails; tools cần credential không chạy.

```text
1. Check KMS reachability + IAM (service account JSON).
2. Check in-memory DEK cache (short-lived) còn không.
3. Fail closed: tools cần credential -> TOOL_CREDENTIAL_UNAVAILABLE (audit).
4. Do NOT fall back to raw/local secret in production.
```

**Resolution:** restore KMS access / rotate service account.
**Follow-up:** review KMS quota (free tier limit).

## Incident Logging

Mọi incident → `audit_events` (operator access) + incident note. Operator queries qua operator API (BYPASSRLS role), không direct DB.

## References

- [Observability + Eval + Ops](observability-evaluation-and-operations.md)
- [Security And Auditability](../03-security/security-and-auditability.md)
- [Data Flow Diagrams](../01-architecture/data-flow-diagrams.md)
- [Operator API](../api-reference/operator-api.md)
