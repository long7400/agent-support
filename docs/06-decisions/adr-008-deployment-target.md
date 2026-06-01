# ADR-008: Deployment Target

- **Status:** accepted
- **Date:** 2026-06-01
- **Deciders:** eng-lead, devops, founder
- **Related:** ADR-006, ADR-007, ADR-001, [phase-0-template-hardening.md](../05-roadmap/phase-0-template-hardening.md)

## Context

Phase 0 cần chốt deployment để: chọn cloud KMS provider (ADR-006 depends), chốt CI/CD, network egress controls, backup/restore. Context: **solo/small team, cost-first**. Tension: multi-tenant SaaS muốn HA/auto-scale/managed KMS, nhưng cost-first muốn ~$50/month.

## Decision

**Single VPS + Docker Compose (Phase 0-3 MVP) + GCP Cloud KMS free tier.** Design portable (Docker + env config + KMS interface) để lift sang managed khi scale, không rebuild.

## Consequences

### Positive
- Cost thấp (Hetzner CX22 €4-7/month hoặc DO $12-24/month).
- Full control, portable design.
- GCP KMS free tier (20K ops/month) đủ MVP, simpler hơn Vault self-host.

### Negative / Costs
- Single VPS = no HA, server crash = downtime.
- Postgres/Qdrant backup tự lo (pg_dump + cron + B2).
- Scale ceiling ~50-200 tenants/VPS.
- Langfuse + Clickhouse RAM tight trên 4GB.

### Follow-up actions
- docker-compose: api, worker, postgres, qdrant, redis, langfuse, caddy/traefik (Phase 0).
- Keep Compose resource guardrails on by default: service CPU/memory caps, Docker log rotation, Prometheus retention, cache maxmemory, and small-Postgres tuning. Raise caps from metrics; do not remove them during MVP.
- GCP KMS service account JSON ngoài git, mount vào container.
- Nightly off-site backup (pg_dump + Qdrant snapshot → B2/Storage Box).
- `CloudKMSProvider` (GCP) behind KMSProvider interface (ADR-006).

## Alternatives Considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| **Single VPS + Compose** | Cost thấp, control, portable | No HA, manual backup | **chosen** |
| GCP Cloud Run + Cloud SQL | Managed, auto-scale | Worker polling không hợp serverless, cold start, cost variable | rejected (later) |
| GKE/EKS/AKS | Full K8s | Setup phức tạp, ops cao, overkill | rejected |
| Fly.io | Đơn giản hơn K8s | Smaller ecosystem, KMS external | rejected (later option) |

## Migration Triggers

Lift VPS → managed (Cloud Run/GKE/Fly.io) khi 1 trong:
- Số tenant >20 hoặc 1 enterprise customer ký SLA HA.
- Postgres size >50GB hoặc query p95 chạm SLO.
- Compliance audit yêu cầu separation of duties (DB tách app).
- VPS RAM/CPU thường xuyên >70%.
- Any required guardrail increase would overcommit the VPS after Langfuse/ClickHouse and core services are included.

## Notes

KMS option B (GCP direct) chọn vì free tier đủ + simpler than Vault. Khi budget tăng/compliance khắt khe → swap Vault Transit qua interface. Langfuse RAM tight → có thể start Langfuse Cloud free tier (ADR-007) rồi self-host khi upgrade VPS.
