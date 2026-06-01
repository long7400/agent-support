# Infra Resource Guardrails Research

---
type: research-report
date: 2026-06-02
scope: docker-compose resource guardrails for Agent Support Phase 0 and future phases
---

## Summary

Goal: keep the local/single-VPS infrastructure from growing unbounded while preserving the Phase 0 topology. The right move is not to remove required services; it is to make heavy services explicit, cap containers, rotate Docker logs, bound metrics retention, and add phase notes for real concurrency/backpressure settings that do not exist yet.

Current local measurement showed the Langfuse profile as the heavy path: ClickHouse about 1.0 GiB, Langfuse web about 700 MiB, Langfuse worker about 387 MiB, while the core app/worker/Postgres/Qdrant/Valkey path stayed much smaller. Therefore the default posture should be:

- `make docker-up`: routine light development.
- `make stack-up`: observability when needed.
- `make stack-up-langfuse`: optional/heavy; use only with RAM headroom or move to Langfuse Cloud on a tight VPS.

## Sources Consulted

| Area | Source | Applied Decision |
| --- | --- | --- |
| Compose service limits | Docker Compose services reference: <https://docs.docker.com/reference/compose-file/services/> | Use `cpus`, `mem_limit`, and per-service `logging` settings. |
| Compose profiles | Docker Compose profiles docs: <https://docs.docker.com/compose/how-tos/profiles/> | Keep Langfuse/edge as opt-in profiles; document heavy profile use. |
| Docker json-file logs | Docker logging driver docs: <https://docs.docker.com/engine/logging/drivers/json-file/> | Add `max-size`/`max-file` rotation to every service. |
| Prometheus retention | Prometheus storage docs: <https://prometheus.io/docs/prometheus/latest/storage/> | Add time and size retention flags to stop unbounded TSDB growth. |
| Redis/Valkey memory behavior | Redis eviction docs: <https://redis.io/docs/latest/develop/reference/eviction/> | Set cache Valkey `maxmemory` below container cap and evict cache keys before OOM. |
| PostgreSQL resources | PostgreSQL resource config docs: <https://www.postgresql.org/docs/current/runtime-config-resource.html> | Keep small `shared_buffers`/`work_mem`; avoid high per-connection memory. |
| PostgreSQL connections | PostgreSQL connection config docs: <https://www.postgresql.org/docs/current/runtime-config-connection.html> | Cap `max_connections` for the small-host Compose baseline. |
| Qdrant config | Qdrant configuration docs: <https://qdrant.tech/documentation/guides/configuration/> | Disable telemetry by env and keep Qdrant under container caps. |
| Langfuse self-host | Langfuse self-host config/scaling docs: <https://langfuse.com/self-hosting/configuration> and <https://langfuse.com/self-hosting/configuration/scaling> | Treat self-host Langfuse v3 as heavy because it brings web, worker, Redis, Postgres, MinIO, and ClickHouse. |

## Repo Findings

- `docker-compose.yml` had healthchecks and profiles, but no service resource caps and no log rotation.
- `prometheus/prometheus.yml` scraped every 15s and Prometheus had no explicit retention flags.
- Valkey was configured with AOF enabled even though ADR-003 says Redis/Valkey is cache + rate-limit only, not outbox.
- Postgres app pool default in `.env.example` was small, but server-side `max_connections` and memory knobs were not set in Compose.
- Phase docs already identify Langfuse + ClickHouse as RAM-tight on a 4GB VPS; this needed executable Compose defaults, not only a risk note.

## Changes Made

- Added Docker json-file log rotation defaults: `DOCKER_LOG_MAX_SIZE=10m`, `DOCKER_LOG_MAX_FILE=3`.
- Added `cpus` and `mem_limit` guardrails for app, worker, Postgres, Valkey, Qdrant, Prometheus, Grafana, cAdvisor, Langfuse services, and Traefik.
- Added Postgres small-host server settings: `max_connections=50`, `shared_buffers=128MB`, `effective_cache_size=512MB`, `work_mem=4MB`.
- Changed app Valkey from AOF-on/unbounded to cache-shaped defaults: AOF off, `maxmemory=192mb`, `allkeys-lru`.
- Kept Langfuse Redis safer for queue semantics: `maxmemory=192mb`, `noeviction`.
- Added Qdrant telemetry disable default.
- Added Prometheus retention flags: `7d` and `1GB`.
- Updated Phase 0, Phase 2, Phase 3, Phase 4, Phase 7, ADR-008, Docker docs, and configuration docs.

## Deferred Phase Settings

| Phase | Setting class | Why deferred |
| --- | --- | --- |
| Phase 2 | Outbox claim batch, delivery concurrency, retry backoff ceiling, per-tenant in-flight cap | Requires real outbox/delivery worker implementation. |
| Phase 3 | Graph wall-time timeout, node retry cap, prompt-visible state size, model/tool-call budget, worker concurrency | Requires domain runtime and mocked replay tests first. |
| Phase 4 | Ingest batch size, embedding concurrency, Qdrant upsert batch, active sync cap per tenant | Requires real RAG ingestion pipeline and benchmark corpus. |
| Phase 7 | Alert thresholds, managed-service migration, Langfuse/ClickHouse sizing | Requires pilot metrics and production ops target. |

## Validation Plan

- `docker compose --env-file .env.development config --quiet`
- `docker compose --profile langfuse --env-file .env.development config --quiet`
- `git diff --check`
- P0 targeted tests if runtime code remains unaffected: `uv run pytest tests/test_p0_infra.py`

## Unresolved Questions

- Exact production caps should be recalibrated from 7-day pilot metrics.
- If Langfuse self-host is required on a 4GB VPS, validate startup and ingestion under the caps before accepting that target.
