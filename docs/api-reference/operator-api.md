# Operator API

Platform operator endpoints cho incident review, trace/run inspection, ops. Auth: operator role (DB-level `app_operator` BYPASSRLS, ADR-002). **Mọi access audited.**

> Operator API là cross-tenant. Mọi truy cập ghi `audit_events` (actor_type=operator) + incident note. Operator không truy cập DB trực tiếp.

## Auth

`Authorization: Bearer <operator-jwt>` — role: platform_operator.

Backend dùng `app_operator` role (BYPASSRLS) cho cross-tenant queries. Audit ghi mọi resource access.

## Incident Replay (runbook 1, 5)

### Get run by trace
`GET /v1/operator/runs?trace_id={uuid}` — hoặc `?message_id=` / `?run_id=`
→ agent_runs + steps + tool_calls + retrieval summary + moderation + delivery + versions @ run time.

### Replay
`POST /v1/operator/runs/{run_id}/replay`
→ replay graph với mocked model/tool outputs (deterministic). Audit `operator.replay`.

## Trace / Run Inspection

### List runs
`GET /v1/operator/runs?tenant_id={uuid}&status=&from=&to=`
→ paginated runs (cross-tenant capable).

### Run detail
`GET /v1/operator/runs/{run_id}`
→ full run record + steps + redacted summaries.

## Sync Operations (Phase 7)

### Retry sync
`POST /v1/operator/sync-jobs/{id}/retry`
### List failed syncs
`GET /v1/operator/sync-jobs?status=failed`

## Outbox / Queue Health (runbook 3)

### Outbox status
`GET /v1/operator/outbox/health`
→ `{ processing_pending, delivery_pending, dead_letter_count, oldest_pending_age }`.

### Reclaim stale
`POST /v1/operator/outbox/reclaim`
→ reclaim `processing` rows > timeout (idempotent). Audit `operator.outbox_reclaim`.

### Dead letter review
`GET /v1/operator/outbox/dead-letter`
`POST /v1/operator/outbox/{id}/requeue` — after idempotency confirm.

## Tenant Incident Controls

### Freeze tenant
`POST /v1/operator/tenants/{id}/freeze` — set suspended (incident). Audit.
### Credential rotate (emergency)
`POST /v1/operator/tenants/{id}/credentials/rotate` — KMS DEK rotate. Audit `operator.credential_rotate`.

## Reports (Phase 7)

### Cost/latency summary
`GET /v1/operator/reports/cost?tenant_id=&from=&to=`
→ aggregate from `model_calls` + metrics.

## Audit Query

`GET /v1/operator/audit?tenant_id=&action=&from=&to=`
→ `audit_events` (operator can query cross-tenant; this query itself audited).

## Security Notes

- Operator role separation of duties: incident response only, not runtime.
- Every operator read/write → audit row (PRD-011, repudiation coverage).
- Credential values never returned (handle/hash only).
- Replay uses mocked outputs (no real destructive action).

## Error Format

```json
{ "error_code": "OPERATOR_FORBIDDEN", "detail": "…", "trace_id": "uuid" }
```

## References

- [Runbooks](../04-observability/runbooks.md)
- [Security And Auditability](../03-security/security-and-auditability.md)
- [ADR-002 Tenant Isolation](../06-decisions/adr-002-tenant-isolation-model.md)
- [Phase 7 Discord Ops](../05-roadmap/phase-7-discord-ops.md)
