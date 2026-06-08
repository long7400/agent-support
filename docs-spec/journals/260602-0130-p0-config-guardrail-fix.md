# P0 Config Guardrail Fix

---
type: journal
date: 2026-06-02
scope: Phase 0 env template and production runtime guardrails
---

## Context

Code review found two Phase 0 risks: host-run defaults in `.env.example` pointed at Docker-only service names, and production guardrails allowed Langfuse tracing to be disabled even though LLM tracing is a project rule.

## What Happened

- Changed host-run defaults so `VALKEY_HOST` stays empty, `QDRANT_URL` uses `localhost:6333`, and `LANGFUSE_HOST` uses `localhost:3001`.
- Added `LANGFUSE_CONTAINER_HOST` for Docker Compose app/worker containers so self-host Langfuse still resolves to `langfuse-web:3000`.
- Added a production guardrail failure for `LANGFUSE_TRACING_ENABLED=false`.
- Added P0 regression tests for env-template host defaults and production tracing enforcement.

## Decisions

- Compose owns internal service aliases; host-run env files should stay on localhost or fallback defaults.
- Development may keep Langfuse tracing disabled, but production must fail closed before untraced LLM calls can run.

## Next

- Existing local `.env.development` files created before this fix may still contain Docker-only host values and should be refreshed manually when testing host-run app commands.
