# Local Infrastructure

Development services:

- PostgreSQL: metadata, migrations, RLS integration tests.
- Redis: future streams and jobs.
- Qdrant: future vector storage.

## Commands

```bash
docker compose -f infra/docker-compose.yml up -d --wait
docker compose -f infra/docker-compose.yml ps
docker compose -f infra/docker-compose.yml down
docker compose -f infra/docker-compose.yml down -v
```

Run migrations after Postgres is healthy:

```bash
uv run alembic upgrade head
```

Run integration tests:

```bash
AGENT_SUPPORT_RUN_INTEGRATION=1 uv run pytest tests/integration
```
