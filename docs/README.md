# Agent Support — Documentation

Source of truth cho việc rebuild Agent Support (community-ops control plane cho nhiều dự án crypto) trên nền FastAPI + LangGraph template. Multi-tenant SaaS từ đầu, ưu tiên tenant isolation, auditability, replayability, security, observability.

> Tài liệu này phản ánh **13 decisions đã chốt**: ADR-001..009 trong `06-decisions/`, và decisions 10..13 trong roadmap/foundation docs. Các open question trong bản draft cũ (`template-rebuild-docs/`) đã được resolve và đóng băng ở đây.

## Baseline Status

- **Frozen baseline:** 2026-06-01.
- **Authority:** numbered folders (`00-foundation`..`07-onboarding`) + `api-reference` win over legacy root docs and root `README.md`.
- **Current code state:** still inherited FastAPI/LangGraph template. Phase 0 owns template hardening/rebrand; this docs freeze does not imply runtime implementation is done.
- **Next implementation gate:** create Phase 0 plan before changing runtime code.

## Reading Order

Numbered folders = reading order. Đọc tuần tự nếu mới vào dự án.

| # | Folder | Nội dung |
| --- | --- | --- |
| 00 | [foundation](00-foundation/) | Mission, scope, PRD, glossary, product principles. |
| 01 | [architecture](01-architecture/) | Target architecture, domain/tenant model, agent design, adapters, data-flow. |
| 02 | [persistence](02-persistence/) | Storage strategy, schema reference, migration rules, vector/RAG storage. |
| 03 | [security](03-security/) | Threat model, controls/audit, authn/authz, secret handling. |
| 04 | [observability](04-observability/) | Observability + eval + ops, metrics catalog, runbooks, eval datasets. |
| 05 | [roadmap](05-roadmap/) | Rebuild roadmap + per-phase design (Phase 0–7). |
| 06 | [decisions](06-decisions/) | ADR records (ADR-001…009) + template. |
| 07 | [onboarding](07-onboarding/) | Dev setup, code standards, contribution flow, glossary quickref. |
| — | [api-reference](api-reference/) | Admin, adapter-ingest, operator API contracts. |

## Decisions Snapshot

| # | Decision | Resolution |
| --- | --- | --- |
| 1 | Vector backend | Qdrant v1 sau `VectorSearchProvider` contract |
| 2 | Tenant isolation | PostgreSQL RLS toàn diện + `SET LOCAL` per-tx + operator `BYPASSRLS` |
| 3 | Graph execution | Postgres outbox + polling worker (`SKIP LOCKED`) + LISTEN/NOTIFY |
| 4 | ORM | SQLAlchemy 2.0 thuần + Pydantic v2 riêng |
| 5 | Tenant auth | JWT user + service principals + `tenant_memberships` |
| 6 | Secret manager | KMS envelope encryption + Postgres credential table |
| 7 | Trace backend | Langfuse self-host + redaction callback |
| 8 | Deployment v1 | Single VPS + Docker Compose + GCP Cloud KMS free tier |
| 9 | Telegram | Per-tenant bot + webhook mode |
| 10 | Knowledge source | Markdown upload Phase 4, URL Phase 5 |
| 11 | Discord | Defer Phase 7, contract Discord-ready từ Phase 2 |
| 12 | Moderation UI | Telegram bot review + minimal API Phase 6 |
| 13 | Retention | 90d chat / 180d runs / 2y audit + per-tenant override + GDPR <30d |

## Conventions

- Mỗi doc <= 800 LOC. File lớn hơn → tách.
- Cross-refs dùng relative path (vd `../06-decisions/adr-002-tenant-isolation-model.md`).
- Filename kebab-case, self-documenting.
- Vietnamese prose + English technical terms (giữ thuật ngữ chuẩn).
- ADR là nơi chốt quyết định; doc khác tham chiếu ADR thay vì lặp lại tranh luận.

## Legacy Template Docs

Các file `.md` ở root `docs/` là **template-level reference docs cũ**. Giữ tạm cho template-specific details cho đến Phase 0 cleanup. Khi conflict, numbered folders thắng.

| Legacy file | Baseline replacement / authority |
| --- | --- |
| `architecture.md` | `01-architecture/system-architecture.md`, `01-architecture/data-flow-diagrams.md` |
| `authentication.md` | `03-security/authn-authz.md`, `api-reference/admin-api.md` |
| `code-standards.md` | `07-onboarding/code-standards.md`, root `AGENTS.md` |
| `configuration.md` | `07-onboarding/getting-started.md`, `03-security/secret-handling.md` |
| `database.md` | `02-persistence/persistence-strategy.md`, `02-persistence/migration-rules.md`, `02-persistence/schema-reference.md` |
| `docker.md` | `05-roadmap/phase-0-template-hardening.md`, `06-decisions/adr-008-deployment-target.md` |
| `evaluation.md` | `04-observability/eval-datasets.md`, `04-observability/observability-evaluation-and-operations.md` |
| `getting-started.md` | `07-onboarding/getting-started.md` |
| `llm-service.md` | `01-architecture/core-agent-design.md`, `04-observability/observability-evaluation-and-operations.md` |
| `memory.md` | `02-persistence/vector-and-rag-storage.md`, `01-architecture/domain-and-tenant-model.md` |
| `observability.md` | `04-observability/observability-evaluation-and-operations.md`, `04-observability/metrics-catalog.md`, `04-observability/runbooks.md` |
| `project-roadmap.md` | `05-roadmap/rebuild-roadmap-and-validation.md` |
| `system-architecture.md` | `01-architecture/system-architecture.md` |

## Related

- Baseline audit: `../plans/reports/260601-1906-docs-baseline-audit.md`
- Brainstorm summary: `../plans/reports/260601-0110-brainstorm-summary-agent-support-rebuild.md`
- Decision transcript: `../discuss.md`
- Research report: `../plans/reports/from-researcher-to-brainstormer-260601-0002-multi-tenant-postgres-isolation-report.md`
- Draft cũ (pre-decision): `../template-rebuild-docs/`
