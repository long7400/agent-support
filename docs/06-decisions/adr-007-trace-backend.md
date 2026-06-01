# ADR-007: Trace Backend / Data Residency

- **Status:** accepted
- **Date:** 2026-06-01
- **Deciders:** eng-lead, ai-eng, security-reviewer, operator
- **Related:** PRD-011, [observability-evaluation-and-operations.md](../04-observability/observability-evaluation-and-operations.md)

## Context

Template tích hợp Langfuse cho LLM tracing. Docs yêu cầu redaction trước export, sampling, và internal audit tables là source of truth (không phải trace SaaS). Crypto tenants sẽ hỏi data residency. Câu hỏi: production tenant traces gửi đi đâu?

## Decision

**Langfuse self-host (Docker Compose) từ Phase 0/1, với redaction callback.** OTLP export defer Phase 7.

## Consequences

### Positive
- Tenant data ở lại infra → compliance dễ, data residency control.
- Giữ eval framework template (dựa trên Langfuse traces).
- 1 Langfuse project per tenant (isolation).

### Negative / Costs
- Ops cost: 1 service nữa (Langfuse + Postgres + Clickhouse), ~2-4GB RAM.
- Backup/upgrade trách nhiệm tự lo.

### Follow-up actions
- Langfuse + Postgres + Clickhouse trong docker-compose (Phase 0).
- Redaction callback wrapper redact secrets/PII trước flush (release gate).
- Sampling per-tenant: 100% Phase 0-3, 10-20% production.
- Internal `agent_runs`/`audit_events` = source of truth (replay không phụ thuộc Langfuse).
- Langfuse retention 30 days.

## Alternatives Considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| Langfuse Cloud | Zero ops, UI tốt | Tenant data leave premise, compliance headache | rejected (fallback only) |
| **Langfuse self-host** | Data residency, keep eval framework | Ops cost, RAM | **chosen** |
| OTLP → Tempo/Jaeger | Vendor-neutral | Mất eval framework, rebuild pipeline | rejected (defer export) |
| Hybrid Langfuse + OTLP | LLM tooling + open standard | Setup phức tạp | defer Phase 7 |
| No external, internal only | Đơn giản | Mất prompt/output inspection, eval không chạy | rejected |

## Notes

Counter-argument: nếu ops capacity thiếu → Langfuse Cloud free tier MVP với exit plan rõ (migrate self-host khi >5 tenants hoặc enterprise customer ký). RAM trên CX22 (4GB) tight với Langfuse + Qdrant → có thể start Cloud rồi self-host khi VPS upgrade.
