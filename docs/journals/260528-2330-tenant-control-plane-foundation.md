---
title: "Tenant Control Plane Foundation"
created: 2026-05-28
plan: "../../plans/260528-2258-tenant-control-plane-foundation/plan.md"
type: implementation
---

# Tenant Control Plane Foundation

## Context

Implemented the Phase 1 control-plane spine from
`plans/260528-2258-tenant-control-plane-foundation/plan.md` after the
FastAPI/Postgres/RLS foundation was in place.

## What Happened

- Added placeholder admin auth through `X-Admin-Token`.
- Added request trace handling with `X-Trace-Id` propagation.
- Added a common API error envelope with `error.code`, `error.message`,
  `error.trace_id`, and `error.details`.
- Extended `tenants` with display/config/version fields.
- Added `tenant_plugins` with Postgres RLS and `FORCE ROW LEVEL SECURITY`.
- Added platform-admin `audit_log` for tenant and plugin mutations.
- Added repository/service boundaries so admin routes stay thin.
- Added admin tenant, plugin, and audit endpoints.
- Added unit and integration coverage for auth, trace, service audit behavior,
  admin API mutation flow, migration rollback, and app-role RLS isolation.
- Added TDD regression coverage for partial tenant patches preserving omitted
  config and unknown-tenant plugin enablement returning `TENANT_NOT_FOUND`.
- Updated README, local env template, architecture docs, technical plan, task
  breakdown, validation checklist, and plan status.

## Decisions

- Kept Qdrant provisioning out of this phase.
- Kept `tenant_platforms`, chat adapters, OAuth/OIDC/JWT, dashboard UI, billing,
  Redis streams, LangGraph, and MCP runtime out of scope.
- Used a privileged admin DB session only behind admin auth and audit.
- Kept tenant-runtime DB access on the app role plus `app.current_tenant`.
- Kept `audit_log` platform-admin only; no app-role grant was added.
- Used concrete repositories rather than a generic repository framework.
- Preserved PATCH semantics with an internal `UNSET` sentinel so omitted fields
  are not treated as empty updates.

## Validation

- `uv run ruff check .`
- `uv run mypy .`
- `uv run pytest tests/unit`
- `docker compose -f infra/docker-compose.yml up -d --wait`
- `uv run alembic downgrade base`
- `uv run alembic upgrade head`
- `AGENT_SUPPORT_RUN_INTEGRATION=1 uv run pytest tests/integration`
- `uv run python scripts/check_secret_scan.py`

## Next

- Replace placeholder admin token with real admin identity when dashboard or
  operator auth enters scope.
- Add Qdrant collection provisioning in the RAG/knowledge-source phase, not in
  this control-plane foundation slice.
- Decide whether plugin config needs a registry-backed schema before MCP/tool
  execution begins.
