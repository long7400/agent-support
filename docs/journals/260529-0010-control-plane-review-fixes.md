---
title: "Control Plane Review Fixes"
created: 2026-05-29
type: fix
---

# Control Plane Review Fixes

## Context

Fixed review blockers found after the Tenant Control Plane Foundation
implementation.

## Root Causes

- Plugin routes returned raw ORM-backed plugin DTOs, so secret-like config keys
  were echoed in API responses.
- `plugin_name` path parameters were unconstrained, so values longer than the DB
  column limit reached SQLAlchemy and returned a raw 500.
- Services imported API-layer `AdminPrincipal` and `ApiError`, reversing the
  intended `core/api -> services -> persistence` direction.
- Admin routes relied on FastAPI response-model serialization instead of explicit
  response DTO conversion.
- Plugin config responses were redacted, but the raw secret-like values were
  still accepted and persisted in `tenant_plugins.config`.
- Pydantic v2 validation errors can include exception objects in `ctx.error`;
  the API error envelope serialized `exc.errors()` directly and could raise
  `PydanticSerializationError` instead of returning a 422 response.
- Credential-like plugin config detection could be bypassed with separators,
  alternative key names, Unicode tricks, or credential header strings.
- The local placeholder admin token was still valid when settings were
  constructed for staging or production-like environments.
- Tenant plugin enable used a select-then-insert pattern, so concurrent
  idempotent `PUT` requests for the same tenant/plugin could raise a unique
  constraint error.
- Empty tenant `PATCH {}` requests returned `200` and wrote a no-op
  `tenant.updated` audit row with identical before/after snapshots.

## Fixes

- Added central service-layer redaction and applied it to plugin responses and
  audit records.
- Added FastAPI `Path` validation for `plugin_name`.
- Moved `AdminPrincipal` and service errors below the API layer.
- Added a service-error handler at the API layer.
- Converted admin route outputs explicitly with Pydantic response DTOs.
- Rejected credential-like plugin config keys before service/repository calls.
- Made API error `details` JSON-safe before serializing the error envelope.
- Hardened credential detection with Unicode normalization, separator-insensitive
  matching, non-ASCII key rejection, and common credential header-value checks.
- Added a settings guard that rejects the local default admin token outside local
  environments.
- Changed tenant plugin enable persistence to a Postgres atomic upsert.
- Rejected empty tenant update request bodies before service/repository calls.
- Added integration regression tests for redacted plugin config and plugin-name
  validation envelopes.
- Added regression coverage proving credential-like plugin config requests return
  422 and leave no persisted `tenant_plugins` row.
- Added regression coverage for credential-key bypass variants, header-value
  smuggling, and production default-token rejection.
- Added regression coverage for concurrent duplicate plugin enable and empty
  tenant patch audit suppression.

## Validation

- `uv run ruff check .`
- `uv run mypy .`
- `uv run pytest tests/unit`
- `AGENT_SUPPORT_RUN_INTEGRATION=1 uv run pytest tests/integration`
- `uv run alembic downgrade base`
- `uv run alembic upgrade head`
- `uv run python scripts/check_secret_scan.py`
