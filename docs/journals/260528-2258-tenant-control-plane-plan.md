---
title: "Tenant Control Plane Foundation Plan"
date: "2026-05-28"
plan: "../../plans/260528-2258-tenant-control-plane-foundation/plan.md"
type: planning
---

# Tenant Control Plane Foundation Plan

## Context

After the infra/FastAPI/RLS foundation merged, Phase 1 needed a focused plan for
the control-plane spine before messaging, RAG, agent runtime, or dashboard work.

## Decisions

- Keep scope to admin API boundary, tenant config, plugin enablement, audit log,
  service/repository convention, and RLS/security verification.
- Use `X-Admin-Token` only as a placeholder admin gate.
- Keep `tenant_platforms`, OAuth/OIDC, Redis messaging, LangGraph, Qdrant/RAG,
  MCP execution, and dashboard UI out of this phase.
- Treat admin-session vs tenant-scoped app-session as an explicit boundary.
- Keep `audit_log` platform-admin only for this slice.

## Verification

- `ck plan validate plans/260528-2258-tenant-control-plane-foundation/plan.md --strict`
- `ck plan status plans/260528-2258-tenant-control-plane-foundation/plan.md`
- `uv run python scripts/check_secret_scan.py`

## Next

Use `/ck:cook /Users/long7400/Project/agent-support--/plans/260528-2258-tenant-control-plane-foundation/plan.md`
after review approval.
