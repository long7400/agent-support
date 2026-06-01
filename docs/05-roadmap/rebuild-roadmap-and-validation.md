# Rebuild Roadmap And Validation

Roadmap rebuild Agent Support trên template, gap map, validation gates, thứ tự triển khai. Per-phase deep design: `phase-N-*.md`.

## Rebuild Strategy

Không port code cũ. Rebuild vertical slices trên template.

Priority order:
1. Template hardening (Phase 0) — migrate SQLAlchemy 2.0, thêm Qdrant/Langfuse/KMS skeleton.
2. Tenant + audit spine (Phase 1) — RLS.
3. Adapter ingest + durable event path (Phase 2) — outbox.
4. Narrow LangGraph domain runtime (Phase 3).
5. Source-backed knowledge retrieval (Phase 4) — Markdown + Qdrant.
6. Capability/tool registry (Phase 5).
7. Moderation enforcement + review (Phase 6) — Telegram bot review.
8. Multi-platform + ops polish (Phase 7) — Discord.

## What Template Already Solves

| Capability | Reuse |
| --- | --- |
| FastAPI app structure | Keep + extend. |
| JWT auth/session | Keep base; add tenant roles + service principals. |
| LangGraph setup | Extend graph → domain workflow. |
| PostgreSQL/Alembic | Keep; add tenant schema + RLS. |
| pgvector/mem0 | Use carefully; **không** auto official knowledge (Qdrant cho RAG). |
| LLM retry/fallback | Keep concept; add tenant budget/policy/versioning. |
| Langfuse/metrics/logging | Keep; add redaction + tenant/run metadata + self-host. |
| Evaluation scaffold | Keep; add product/security metrics. |
| Docker/Makefile | Keep; add adapters/workers/qdrant/langfuse. |

## Main Gaps To Build

| Gap | Why |
| --- | --- |
| Tenant model + membership | Template user/session ≠ tenant SaaS. |
| RLS isolation | Cannot risk cross-tenant leak. |
| ORM migration SQLAlchemy 2.0 | RLS pattern + DTO separation (ADR-004). |
| Adapter principal + platform mapping | Trusted tenant resolution. |
| Durable chat events + outbox | Replay, idempotency, async graph (ADR-003). |
| Domain graph workflow | Generic loop lacks policy gates. |
| Agent run/step records | Audit + debugging. |
| Source-backed RAG (Qdrant) | mem0 ≠ curated knowledge (ADR-001). |
| Capability registry/tool proxy | Multi-tenant tool safety. |
| KMS secret handles | Raw credentials cannot live in config (ADR-006). |
| Product eval datasets | Generic helpfulness not enough. |

## Phase Summary

| Phase | Goal | Design doc |
| --- | --- | --- |
| 0 | Template hardening | [phase-0-template-hardening.md](phase-0-template-hardening.md) |
| 1 | Tenant control plane (RLS) | [phase-1-tenant-control-plane.md](phase-1-tenant-control-plane.md) |
| 2 | Platform ingest + delivery (outbox) | [phase-2-platform-ingest.md](phase-2-platform-ingest.md) |
| 3 | Agent runtime skeleton | [phase-3-agent-runtime.md](phase-3-agent-runtime.md) |
| 4 | Knowledge + RAG (Markdown + Qdrant) | [phase-4-knowledge-rag.md](phase-4-knowledge-rag.md) |
| 5 | Capability registry + tools | [phase-5-capability-tools.md](phase-5-capability-tools.md) |
| 6 | Moderation enforcement + review | [phase-6-moderation.md](phase-6-moderation.md) |
| 7 | Discord, ops, reports, dashboard | [phase-7-discord-ops.md](phase-7-discord-ops.md) |

## Exit Criteria (per phase)

- **Phase 0:** fresh clone runs API + migrations; SQLAlchemy 2.0 migration done; Qdrant + Langfuse in compose; KMSProvider skeleton; secret scan clean.
- **Phase 1:** Tenant A cannot read/write Tenant B (RLS, app_user role); config mutations audited; disabled tenant blocked; migration up/down.
- **Phase 2:** Telegram message resolves tenant + persists trusted event; duplicate idempotent; adapter cannot supply tenant id; outbound idempotent; unknown mapping fails closed; outbox worker processes events.
- **Phase 3:** saved event replays with mocked outputs; tenant id immutable; no real LLM in unit tests; outbound only after policy; run/step records created.
- **Phase 4:** Tenant A cannot retrieve Tenant B chunks; empty/stale/low-confidence refuses; source update/delete/tombstone hides old chunks; activation prevents partial visibility.
- **Phase 5:** disabled tool cannot execute; schemas enforced; denials audited; secrets absent from logs/traces/config.
- **Phase 6:** shadow/propose/enforce behave as configured; destructive actions audited+idempotent; review override works (Telegram bot); no model text executes destructive action.
- **Phase 7:** Discord reuses normalized contracts; operator debugs bad answer trace→sources→tools→actions; dashboard/API supports admin ops without DB access.

## Validation Matrix

| Area | Gate |
| --- | --- |
| Code quality | ruff, pyright, pytest. |
| Migrations | Alembic upgrade + downgrade. |
| Secrets | detect-secrets. |
| Tenant DB | Cross-tenant denial (least-priv role). |
| Vector | Cross-tenant + visibility denial (Qdrant app-layer). |
| Adapter | Invalid credential, scope mismatch, duplicate message. |
| Graph | Replay deterministic (mocked). |
| Tools | disabled/missing/invalid/timeout/credential failure. |
| Moderation | shadow/propose/enforce fixtures. |
| Observability | redaction + sampling. |
| Eval | product threshold for support/moderation/tool safety. |

## Suggested Local Commands

```bash
make install
make docker-compose-up ENV=development
make migrate
pytest
ruff check .
pyright app evals
make eval-quick
detect-secrets scan --baseline .secrets.baseline
```

Schema changes:
```bash
make migration MSG="describe change"
make migrate
make migrate-downgrade
make migrate
```

## Risk Register

| Risk | Mitigation |
| --- | --- |
| Template mem0 unsafe community memory | Disable/restrict until governance. |
| RLS friction với SQLAlchemy async | Helper `with_tenant_context()`, raw SQL policies Phase 1. |
| Generic chat graph ships as product | Replace with domain graph Phase 3. |
| Web search hallucination | Disable default; policy-controlled tool only. |
| Vector backend churn | `VectorSearchProvider` contract trước Qdrant. |
| Overbuilding plugins | Built-in capabilities + audit first. |
| Moderation harm | Shadow/propose first; enforce after Telegram review UX. |
| Trace data leakage | Redaction/sampling before production traces. |
| Solo + SaaS HA tension | Portable design + single-VPS MVP + migrate trigger (ADR-008). |

## References

- [Project Brief](../00-foundation/project-brief.md)
- [Product Requirements](../00-foundation/product-requirements.md)
- [ADR index](../06-decisions/)
- Phase docs in this folder.
