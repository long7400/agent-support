# Phase 7: Discord, Ops, Reports, And Dashboard

**Goal:** expand operations sau khi Telegram path safe. Discord deferred here (Decision 11) — contract đã Discord-ready từ Phase 2.

## Scope (outline)

- Discord adapter (reuse normalized contracts).
- Trace/run inspection APIs (operator).
- Sync retry APIs.
- Reports + scheduled summaries.
- Cost/latency dashboards.
- Operator runbooks (xem [runbooks.md](../04-observability/runbooks.md)).
- Web UI cho moderation review (presentation trên Phase 6 API).
- Declarative partitioning by month cho `chat_events` (scale).
- OAuth/SSO admin login.

## Discord Adapter (Decision 11)

Contract đã ready từ Phase 2 (mock-verified). Phase 7 build real impl:
- Gateway vs interactions/webhook mode.
- Message content privileged intent enrollment.
- Guild/channel/thread mapping.
- Bot permissions by action type.
- Reconnect/resume strategy.
- Slash commands/admin actions.
- Discord formatting + length constraints.

Reuse: normalized inbound contract, trusted tenant resolution, agent graph, outbound envelope, moderation policy matrix.

> Promote sớm lên Phase 5 nếu ≥30% pilot prospects yêu cầu Discord.

## Exit Criteria

- [ ] Discord reuses normalized contracts (no graph change).
- [ ] Operator debugs bad answer from trace → sources → tools → actions.
- [ ] Dashboard/API supports core admin ops without DB access.

## Migration Triggers Trigger (ADR-008)

Lift VPS → managed khi: >20 tenants / enterprise SLA HA / Postgres >50GB / VPS >70% capacity. Partition chat_events; consider managed Postgres (Neon/Supabase), worker scale (Swarm/Fly.io/Cloud Run).

## Resource And Ops Follow-Up

- Review every `*_CPU_LIMIT`, `*_MEM_LIMIT`, Prometheus retention, and Docker log rotation value against 7-day pilot metrics before production launch.
- If Langfuse self-host remains enabled, size ClickHouse from real trace volume or move tracing to Langfuse Cloud/managed ClickHouse before raising app concurrency.
- Add alerts for container memory >70%, Prometheus retention truncation, queue age, DB connection saturation, Qdrant latency, and Langfuse ingestion lag.

## References

- [ADR-008 Deployment Target](../06-decisions/adr-008-deployment-target.md)
- [Adapters And Integrations (Discord)](../01-architecture/adapters-and-integrations.md)
- [Operator API](../api-reference/operator-api.md)
- [Runbooks](../04-observability/runbooks.md)
