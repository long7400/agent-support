# Validation Checklist

## Pre-Merge

- [ ] Tests pass locally.
- [ ] Type checks pass.
- [ ] Lint passes.
- [ ] No secrets in diff.
- [ ] Migrations upgrade from empty DB.
- [ ] Migrations downgrade or rollback path is documented.
- [ ] New tenant-owned tables have `tenant_id`.
- [ ] New tenant-owned tables have RLS policy.
- [ ] New tenant-owned tables use `FORCE ROW LEVEL SECURITY`.
- [ ] RLS tests use app role, not owner/superuser.
- [ ] Admin routes reject missing or invalid `X-Admin-Token`.
- [ ] Staging/production settings reject the local default admin token.
- [ ] API errors include `error.code`, `error.message`, `error.trace_id`, and `error.details`.
- [ ] Config mutations write audit rows with trace id.
- [ ] Plugin config requests reject credential-like keys, separator/case/Unicode
      variants, and common credential header-value smuggling before persistence.
- [ ] Plugin config responses redact secret-like keys and credential-like values.
- [ ] Plugin route parameters validate before hitting database constraints.
- [ ] Route handlers call services/repositories instead of raw SQL.
- [ ] New external calls have timeout.
- [ ] Redis Streams publishers use bounded `XADD MAXLEN ~`.
- [ ] Redis chat transport uses `noeviction` and explicit local memory limits.
- [ ] Redis backpressure tests cover warn-only and reject thresholds.
- [ ] Worker ACK happens only after downstream side effects succeed.
- [ ] Internal ingest writes tenant-owned rows through app role plus tenant context.
- [ ] Redis publish failures leave a durable pending outbox row for retry.
- [ ] New tool calls are audited.
- [ ] Docs updated for changed contracts.

Current local commands:

```text
uv run ruff check .
uv run mypy .
uv run pytest tests/unit
docker compose -f infra/docker-compose.yml up -d --wait
docker compose -f infra/docker-compose.yml exec -T redis redis-cli CONFIG GET maxmemory maxmemory-policy maxmemory-clients
uv run alembic upgrade head
AGENT_SUPPORT_RUN_INTEGRATION=1 uv run pytest tests/integration
uv run python scripts/check_secret_scan.py
```

When migrations change:

```text
uv run alembic downgrade base
uv run alembic upgrade head
```

## Tenant Isolation

- [ ] API rejects missing tenant context.
- [ ] Tenant A cannot read tenant B rows.
- [ ] Tenant A cannot query tenant B Qdrant chunks.
- [ ] Tenant A cannot invoke tenant B enabled tools.
- [ ] Tenant A cannot access tenant B source documents.
- [ ] Redis envelopes include tenant id and trace id.
- [ ] Background jobs re-load and verify tenant context before doing work.
- [ ] Normalized adapter requests cannot supply trusted `tenant_id`.
- [ ] Duplicate platform messages reuse one `chat_event_id`.
- [ ] Unknown platform mappings fail closed before persistence.

## Agent Safety

- [ ] LLM output is policy-checked before sending.
- [ ] Tool calls are allowlisted per tenant.
- [ ] Tool input schemas reject unknown fields.
- [ ] Tool output is bounded before entering prompts.
- [ ] Prompt templates are validated.
- [ ] Low-confidence RAG answers refuse or escalate.
- [ ] Destructive moderation actions require explicit tenant policy.

## RAG Quality

- [ ] Source sync is idempotent.
- [ ] Chunk payload includes tenant id, source id, document id, and version.
- [ ] Query filters by tenant id.
- [ ] Answers include citations when source-backed.
- [ ] No answer is generated from empty retrieval unless fallback policy allows it.
- [ ] Evaluation set covers official links, tokenomics, roadmap, scam examples, and stale docs.

## TurboVec Accelerator Gate

- [ ] Qdrant baseline provider is implemented first.
- [ ] TurboVec is behind `RAG_ACCELERATOR=turbovec`.
- [ ] TurboVec can be disabled without data migration.
- [ ] TurboVec tenant/source filtering matches Qdrant provider behavior.
- [ ] TurboVec benchmark uses the same fixture corpus as Qdrant.
- [ ] Recall, p95 latency, RAM, build time, and persist/load time are recorded.
- [ ] Persist/load works in the deployed runtime layout.
- [ ] Index rebuild from Qdrant/source chunks is tested.
- [ ] Corrupt or missing TurboVec index falls back to Qdrant or fails closed.
- [ ] ADR 0002 is updated before changing the default.

## Observability

- [ ] Every request has `trace_id`.
- [ ] Every graph node logs latency and status.
- [ ] Every LLM call records provider, model, token usage, and error.
- [ ] Every tool call records status, timeout, and redacted summary.
- [ ] Every moderation action records policy version.
- [ ] Dashboards show p95 latency, error rate, tool failures, sync failures, and token cost.

## Production Release

- [ ] Staging deployment passed smoke tests.
- [ ] Backup and restore tested.
- [ ] Rollback image is available.
- [ ] Migration plan reviewed.
- [ ] Secrets are configured outside git.
- [ ] Rate limits are configured.
- [ ] Alert routes are configured.
- [ ] Incident runbook exists.
- [ ] One sandbox tenant passes end-to-end Telegram or Discord flow.
