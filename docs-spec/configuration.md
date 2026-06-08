# Configuration

All configuration is read from environment variables. Use `.env.development`, `.env.staging`, or `.env.production` — the app loads the right file based on the `APP_ENV` variable.

Copy `.env.example` to get started:

```bash
cp .env.example .env.development
```

---

## Application

| Variable | Default | Description |
| --- | --- | --- |
| `APP_ENV` | `development` | Environment: `development`, `staging`, `production`, `test` |
| `PROJECT_NAME` | `FastAPI LangGraph Template` | Displayed in API docs and logs |
| `VERSION` | `1.0.0` | API version |
| `DEBUG` | `false` | Enables debug logging and profiling middleware |
| `API_V1_STR` | `/api/v1` | API prefix |
| `ALLOWED_ORIGINS` | `*` | Comma-separated CORS origins |

---

## LLM

| Variable | Default | Required | Description |
| --- | --- | --- | --- |
| `OPENAI_API_KEY` | — | Yes | OpenAI API key |
| `DEFAULT_LLM_MODEL` | `gpt-5-mini` | No | Starting model — see [LLM Service](llm-service.md) for fallback order |
| `DEFAULT_LLM_TEMPERATURE` | `0.2` | No | Temperature for chat completions |
| `MAX_TOKENS` | `2000` | No | Max tokens per LLM response |
| `MAX_LLM_CALL_RETRIES` | `3` | No | Retries per model before switching to fallback |
| `LLM_TOTAL_TIMEOUT` | `60` | No | Max seconds for the entire fallback loop |
| `SESSION_NAMING_ENABLED` | `true` | No | Auto-generate a session title from the user's first message using an LLM background task |

---

## Long-term memory

| Variable | Default | Description |
| --- | --- | --- |
| `LONG_TERM_MEMORY_COLLECTION_NAME` | `longterm_memory` | pgvector collection name |
| `LONG_TERM_MEMORY_MODEL` | `gpt-5-nano` | LLM used by mem0 to extract memories |
| `LONG_TERM_MEMORY_EMBEDDER_MODEL` | `text-embedding-3-small` | Embedding model for semantic search |

---

## Database

| Variable | Default | Description |
| --- | --- | --- |
| `POSTGRES_HOST` | `localhost` | PostgreSQL host |
| `POSTGRES_PORT` | `5432` | PostgreSQL port |
| `POSTGRES_DB` | `food_order_db` | Database name |
| `POSTGRES_USER` | `postgres` | Database user |
| `POSTGRES_PASSWORD` | `postgres` | Database password |
| `POSTGRES_POOL_SIZE` | `20` | SQLAlchemy connection pool size |
| `POSTGRES_MAX_OVERFLOW` | `10` | Max overflow connections above pool size |
| `POSTGRES_MAX_CONNECTIONS` | `50` | PostgreSQL server connection cap in Docker Compose |
| `POSTGRES_SHARED_BUFFERS` | `128MB` | PostgreSQL shared buffer setting for small-host Compose |
| `POSTGRES_EFFECTIVE_CACHE_SIZE` | `512MB` | PostgreSQL planner cache-size hint for small-host Compose |
| `POSTGRES_WORK_MEM` | `4MB` | Per-sort/hash memory cap for PostgreSQL queries |

---

## Auth

| Variable | Default | Required | Description |
| --- | --- | --- | --- |
| `JWT_SECRET_KEY` | — | Yes | Secret used to sign JWT tokens — use a long random string in production |
| `JWT_ALGORITHM` | `HS256` | No | JWT signing algorithm |
| `JWT_ACCESS_TOKEN_EXPIRE_DAYS` | `30` | No | Token lifetime in days |

---

## Cache (Valkey/Redis — optional)

When `VALKEY_HOST` is set, the app uses Valkey/Redis for memory search caching and rate limiting. When absent, it falls back to an in-memory TTL cache (not shared across instances).

| Variable | Default | Description |
| --- | --- | --- |
| `VALKEY_HOST` | `` (disabled) | Valkey/Redis host — leave empty to use in-memory fallback |
| `VALKEY_PORT` | `6379` | Port |
| `VALKEY_DB` | `0` | Database index |
| `VALKEY_PASSWORD` | `` | Password (if required) |
| `VALKEY_MAX_CONNECTIONS` | `20` | Connection pool size |
| `CACHE_TTL_SECONDS` | `60` | TTL for cached memory search results |
| `VALKEY_APPENDONLY` | `no` | Docker Compose Valkey persistence mode; cache/rate-limit data is not a durable queue |
| `VALKEY_MAXMEMORY` | `192mb` | Valkey maxmemory below the container memory cap |
| `VALKEY_MAXMEMORY_POLICY` | `allkeys-lru` | Evict least-recently-used cache/rate-limit keys before OOM |

---

## Observability (Langfuse)

| Variable | Default | Description |
| --- | --- | --- |
| `LANGFUSE_TRACING_ENABLED` | `true` | Set to `false` to disable tracing entirely |
| `LANGFUSE_PUBLIC_KEY` | — | Langfuse project public key |
| `LANGFUSE_SECRET_KEY` | — | Langfuse project secret key |
| `LANGFUSE_HOST` | `https://cloud.langfuse.com` | Langfuse host for host-run processes (self-hosted or cloud) |
| `LANGFUSE_CONTAINER_HOST` | `http://langfuse-web:3000` | Docker Compose app/worker override for the internal Langfuse service or a cloud URL |

---

## Rate limiting

| Variable | Default | Description |
| --- | --- | --- |
| `RATE_LIMIT_DEFAULT` | `200 per day, 50 per hour` | Fallback limit |
| `RATE_LIMIT_CHAT` | `30 per minute` | POST /chat |
| `RATE_LIMIT_CHAT_STREAM` | `20 per minute` | POST /chat/stream |
| `RATE_LIMIT_MESSAGES` | `50 per minute` | GET/DELETE /messages |
| `RATE_LIMIT_LOGIN` | `20 per minute` | POST /auth/login |
| `RATE_LIMIT_REGISTER` | `10 per hour` | POST /auth/register |

When Valkey is configured, rate limiting is shared across all app instances. Without it, limits are per-process.

---

## Profiling (debug only)

Only active when `DEBUG=true`. Profiles every request and saves a JSON report when the request exceeds the threshold.

| Variable | Default | Description |
| --- | --- | --- |
| `PROFILING_DIR` | `/tmp/fastapi_profiles` | Directory for profile JSON files |
| `PROFILING_THRESHOLD_SECONDS` | `2.0` | Minimum wall time to trigger saving a profile. Set to `0` to profile every request. |

---

## Docker resource guardrails

These variables are consumed by `docker-compose.yml`, not by the FastAPI process. Defaults target local development and a cost-first single VPS. Raise them only with host metrics in hand.

| Variable | Default | Description |
| --- | --- | --- |
| `DOCKER_LOG_MAX_SIZE` | `10m` | Per-container json-file log segment size |
| `DOCKER_LOG_MAX_FILE` | `3` | Number of retained log segments |
| `APP_CPU_LIMIT` / `APP_MEM_LIMIT` | `1.0` / `512m` | FastAPI container cap |
| `WORKER_CPU_LIMIT` / `WORKER_MEM_LIMIT` | `0.5` / `384m` | Runtime worker cap |
| `QDRANT_CPU_LIMIT` / `QDRANT_MEM_LIMIT` | `1.0` / `768m` | Qdrant container cap |
| `QDRANT_TELEMETRY_DISABLED` | `true` | Disable Qdrant telemetry in local/small-host stacks |
| `PROMETHEUS_CPU_LIMIT` / `PROMETHEUS_MEM_LIMIT` | `0.5` / `384m` | Prometheus container cap |
| `PROMETHEUS_RETENTION_TIME` | `7d` | Time retention for Prometheus TSDB |
| `PROMETHEUS_RETENTION_SIZE` | `1GB` | Size retention for Prometheus TSDB |
| `GRAFANA_CPU_LIMIT` / `GRAFANA_MEM_LIMIT` | `0.5` / `256m` | Grafana container cap |
| `CADVISOR_CPU_LIMIT` / `CADVISOR_MEM_LIMIT` | `0.25` / `128m` | cAdvisor container cap |
| `LANGFUSE_*_CPU_LIMIT` / `LANGFUSE_*_MEM_LIMIT` | see `.env.example` | Optional self-host Langfuse profile caps; ClickHouse remains the heaviest container |

---

## Logging

| Variable | Default (dev) | Default (prod) | Description |
| --- | --- | --- | --- |
| `LOG_LEVEL` | `DEBUG` | `WARNING` | Log level |
| `LOG_FORMAT` | `console` | `json` | `console` for coloured dev output, `json` for structured production logs |
