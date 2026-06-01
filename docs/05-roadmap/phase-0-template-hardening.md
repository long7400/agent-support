# Phase 0: Template Hardening

**Goal:** make template ready for product work. Tận dụng quyết định đã chốt: migrate ORM, thêm infra services, set portable foundation.

## Scope

- Confirm template baseline chạy (clone → API + migrations + tests).
- **Migrate SQLModel → SQLAlchemy 2.0 thuần + Pydantic v2 riêng** (ADR-004).
- Thêm Qdrant + Langfuse self-host vào docker-compose (ADR-001, ADR-007).
- `KMSProvider` interface skeleton + `LocalKMSProvider`/`CloudKMSProvider` stub (ADR-006, ADR-008).
- Disable/restrict web search + automatic long-term memory trong default community mode.
- Set project naming + environment defaults (production-safe).
- Add product docs (this `docs/`) vào repo.

## Deliverables

### ORM Migration (ADR-004)
- Replace SQLModel base với SQLAlchemy 2.0 `DeclarativeBase` + `Mapped[]` typing.
- Tách persistence model khỏi API DTO (Pydantic v2 schemas riêng).
- Update template auth.py + session model (2 file chính chạm).
- Async session factory với asyncpg.
- Helper `with_tenant_context(session, tenant_id)` stub (RLS dùng Phase 1).
- Verify Alembic autogenerate works với new base.

### Infra (docker-compose, ADR-008)
```text
api          (FastAPI)
worker       (outbox consumer, same image diff command — skeleton)
postgres     (16+, RLS-ready; pgvector optional vì Qdrant cho RAG)
qdrant       (new)
redis        (cache + rate limit only)
langfuse     (+ its own postgres + clickhouse)
caddy/traefik (reverse proxy)
```
- GCP Cloud KMS: service account JSON mount, ngoài git.
- Small-host guardrails: Docker log rotation, service CPU/memory caps, Prometheus retention, Valkey maxmemory policy, Postgres small-pool tuning, Qdrant telemetry disabled.

### KMSProvider Skeleton (ADR-006)
```python
class KMSProvider(Protocol):
    async def encrypt(self, plaintext: bytes) -> str: ...
    async def decrypt(self, handle: str) -> bytes: ...
```
- `LocalKMSProvider` (dev) + `CloudKMSProvider` (GCP stub).
- Pre-flight: production reject LocalKMSProvider (fail closed).

### Risky Defaults Control
- DuckDuckGo / web search KHÔNG expose mặc định.
- mem0 automatic memory disable/restrict cho community mode.
- Environment sample review: production-safe defaults, no demo secrets.

## Exit Criteria

- [x] Fresh clone runs API + migrations (SQLAlchemy 2.0).
- [x] `make docker-compose-up ENV=development` brings up api/worker/postgres/qdrant/valkey/metrics.
- [x] `make stack-up-langfuse ENV=development` brings up optional self-host Langfuse profile.
- [x] Secret scan clean (detect-secrets).
- [x] Baseline tests pass.
- [x] `make typecheck` (pyright) clean với new ORM.
- [x] KMSProvider skeleton + production pre-flight rejects local.
- [x] Risky defaults (web search, auto memory) documented + controlled.
- [x] Infra resource guardrails documented + encoded in Compose/env defaults.
- [x] docs/ in repo.

## Validation

```bash
make install
make docker-compose-up ENV=development
make stack-up-langfuse ENV=development   # optional if local resources allow ClickHouse
make migrate
pytest
make check          # lint + typecheck
detect-secrets scan --baseline .secrets.baseline
```

## Risks

| Risk | Mitigation |
| --- | --- |
| ORM migration breaks template auth | Migrate incrementally; keep auth tests green. |
| Langfuse + Clickhouse RAM trên CX22 (4GB) | Start Langfuse Cloud free tier nếu VPS tight; self-host khi upgrade (ADR-007 exit plan). |
| GCP KMS setup friction | LocalKMSProvider cho dev; CloudKMSProvider chỉ cần production. |
| Compose caps quá thấp cho pilot data thật | Raise từng `*_MEM_LIMIT`/`*_CPU_LIMIT` bằng metrics, không bỏ caps hoàn toàn. |

## References

- [ADR-004 ORM Choice](../06-decisions/adr-004-orm-choice.md)
- [ADR-008 Deployment Target](../06-decisions/adr-008-deployment-target.md)
- [Getting Started](../07-onboarding/getting-started.md)
