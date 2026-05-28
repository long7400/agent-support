---
title: "Infra FastAPI RLS Foundation"
created: 2026-05-28
plan: "../../plans/260528-1910-infra-fastapi-rls-foundation/plan.md"
---

# Infra FastAPI RLS Foundation

## Context

Implemented first foundation slice from `plans/260528-1910-infra-fastapi-rls-foundation/plan.md`.

## What Happened

- Added production-shaped Python layout under `core/`.
- Added FastAPI `/healthz`.
- Added Docker Compose for Postgres, Redis, Qdrant.
- Added SQLAlchemy, Alembic, and first RLS-protected `tenants` / `chat_events` schema.
- Added app-role RLS tests.
- Added CI, local validation docs, and secret scan wrapper that fails on findings.

## Decisions

- Keep Redis and Qdrant infra-only in this slice.
- Use a non-superuser app role for RLS tests.
- Use `docker compose up -d --wait` in docs/CI to avoid DB readiness races.

## Validation

- `uv run ruff check .`
- `uv run mypy .`
- `uv run pytest tests/unit`
- `AGENT_SUPPORT_RUN_INTEGRATION=1 uv run pytest tests/integration`
- `uv run alembic downgrade base`
- `uv run alembic upgrade head`
- `uv run python scripts/check_secret_scan.py`
