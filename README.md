# Agent Support

Production-shaped foundation for a tenant-isolated crypto community support platform.

## Quick Start

Install dependencies:

```bash
uv sync --dev
```

Start local services:

```bash
docker compose -f infra/docker-compose.yml up -d --wait
```

Run migrations:

```bash
uv run alembic upgrade head
```

Start API:

```bash
uv run uvicorn core.api.main:app --reload
```

Health check:

```bash
curl http://127.0.0.1:8000/healthz
```

Create a local tenant through the placeholder admin API:

```bash
curl -X POST http://127.0.0.1:8000/admin/tenants \
  -H 'Content-Type: application/json' \
  -H 'X-Admin-Token: local-admin-token' \
  -d '{"slug":"demo-tenant","display_name":"Demo Tenant","config":{"persona":"helpful"}}'
```

`X-Admin-Token` is a local placeholder gate, not production auth.

## Validation

```bash
uv run ruff check .
uv run mypy .
uv run pytest tests/unit
docker compose -f infra/docker-compose.yml up -d --wait
uv run alembic downgrade base
uv run alembic upgrade head
AGENT_SUPPORT_RUN_INTEGRATION=1 uv run pytest tests/integration
uv run python scripts/check_secret_scan.py
```

Integration tests require Postgres from `infra/docker-compose.yml` and migrated schema.

Local variable names are documented in `config/local-env.template`.
