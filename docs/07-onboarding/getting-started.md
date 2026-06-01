# Getting Started

Dev local setup cho Agent Support (rebuild). Phản ánh stack đã chốt: SQLAlchemy 2.0, Qdrant, Langfuse self-host, outbox worker.

## Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) — `pip install uv`
- Docker + Docker Compose
- OpenAI/Anthropic API key
- (Production) GCP service account JSON cho Cloud KMS (ADR-008)

## Quick Start (Docker)

```bash
git clone <repo-url> agent-support
cd agent-support

cp .env.example .env.development
# Required: OPENAI_API_KEY (or ANTHROPIC), JWT_SECRET_KEY
# Dev KMS: KMS_PROVIDER=local (LocalKMSProvider — reject in prod)
# Optional: LANGFUSE_* (or LANGFUSE_TRACING_ENABLED=false)

make install                              # deps + pre-commit
make docker-compose-up ENV=development    # api + worker + postgres + qdrant + redis + langfuse
make migrate                              # Alembic migrations (+ RLS policies)
```

Open [http://localhost:8000/docs](http://localhost:8000/docs).

## Services (docker-compose, ADR-008)

| Service | Port | Role |
| --- | --- | --- |
| api | 8000 | FastAPI: webhook ingest + admin/operator API |
| worker | — | Outbox consumer (graph + delivery) |
| postgres | 5432 | Source of truth, RLS enforced |
| qdrant | 6333 | Vector backend (ADR-001) |
| redis | 6379 | Cache + rate limit only |
| langfuse | 3000 | Trace backend self-host (ADR-007) |

> Dev: bind internal services tới localhost. Production single VPS: chỉ `api` (qua caddy/traefik) public.

## Quick Commands (Makefile)

```bash
make dev          # dev server hot reload (port 8000)
make lint         # ruff check .
make format       # ruff format .
make typecheck    # pyright (standard mode) — must pass
make check        # lint + typecheck
make migrate      # alembic upgrade
make migration MSG="..."   # new migration
make migrate-downgrade     # rollback
make eval-quick   # LLM evals default
detect-secrets scan --baseline .secrets.baseline
```

## First Tenant Flow (after Phase 1+)

```text
1. Register user -> JWT.
2. Operator create tenant -> tenant_memberships(admin).
3. Configure tenant (persona, official_links, moderation_mode).
4. Telegram: BotFather token -> /v1/admin/telegram/setup -> KMS encrypt -> webhook.
5. Upload knowledge (Markdown, Phase 4).
6. Enable capabilities (rag.search default).
```

API contracts: [admin-api.md](../api-reference/admin-api.md).

## Customising

| What | Where |
| --- | --- |
| Agent prompts | `app/core/prompts/` |
| Graph nodes | `app/core/langgraph/` |
| LLM models/fallback | `app/services/llm.py` |
| Capability manifest | manifest registry (Phase 5) |
| Vector provider | `VectorSearchProvider` impl (Qdrant) |

## Pre-commit

Hooks run on `git commit`: trailing whitespace, YAML/TOML/JSON validation, secret detection (detect-secrets), ruff lint + format. Manual: `make pre-commit`.

## Troubleshooting

- **DB connection error:** ensure postgres up + `POSTGRES_*` match. `make docker-compose-up` handles it.
- **RLS denies query unexpectedly:** check `SET LOCAL app.current_tenant` set trong transaction (`db.begin()`).
- **detect-secrets false positive:** add `# pragma: allowlist secret` cuối dòng.
- **Langfuse errors:** `LANGFUSE_TRACING_ENABLED=false` để skip dev.
- **Production startup fails KMS:** production reject LocalKMSProvider — set CloudKMSProvider (ADR-006).

## References

- [Code Standards](code-standards.md)
- [Contribution Flow](contribution-flow.md)
- [Phase 0 Template Hardening](../05-roadmap/phase-0-template-hardening.md)
- [Glossary Quickref](glossary-quickref.md)
