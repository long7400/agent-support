# Rebuild Roadmap And Validation

## Mục đích

Tài liệu này đưa ra roadmap xây lại Agent Support trên template mới, gap map, validation gates, và thứ tự triển khai ưu tiên.

## Đối tượng đọc

Product owner, engineering lead, backend engineer, AI engineer, QA, operator, và security reviewer.

## Rebuild Strategy

Do not port old code. Rebuild vertical slices on the template.

Order of priority:

1. Tenant and audit spine.
2. Adapter ingest and durable event path.
3. Narrow LangGraph domain runtime.
4. Source-backed knowledge retrieval.
5. Capability/tool registry.
6. Moderation enforcement and review.
7. Multi-platform and operations polish.

## What The Template Already Solves

| Capability | Reuse |
| --- | --- |
| FastAPI app structure | Keep and extend. |
| JWT auth/session | Keep as user/session base; add tenant roles. |
| LangGraph setup | Extend graph into domain workflow. |
| PostgreSQL/Alembic | Keep; add tenant schema and isolation. |
| pgvector/mem0 | Use carefully; not automatic official knowledge. |
| LLM retry/fallback | Keep concept; add tenant budget/policy/versioning. |
| Langfuse/metrics/logging | Keep; add redaction and tenant/run metadata. |
| Evaluation scaffold | Keep; add product/security metrics. |
| Docker/Makefile | Keep; add adapters/workers/backends as needed. |

## Main Gaps To Build

| Gap | Why it matters |
| --- | --- |
| Tenant model and membership | Template user/session is not tenant SaaS. |
| Tenant isolation/RLS/equivalent | Product cannot risk cross-tenant data leak. |
| Adapter principal and platform mapping | External events need trusted tenant resolution. |
| Durable chat events and outbound delivery | Needed for replay, idempotency, and incident review. |
| Domain graph workflow | Generic chat loop lacks support/moderation/onboarding policy gates. |
| Agent run/step records | Needed for audit and debugging. |
| Source-backed RAG model | mem0 is not curated official tenant knowledge. |
| Capability registry/tool proxy | Direct tool binding is unsafe for multi-tenant tools. |
| Secret handles | Raw credentials cannot live in config/prompt/logs. |
| Product eval datasets | Generic helpfulness evals are not enough. |

## Phase 0: Template Hardening

Goal: make template ready for product work.

Deliverables:

- Confirm local install, Docker, migrations, tests.
- Set project naming and environment defaults.
- Review environment sample for production-safe defaults.
- Disable or restrict web search and automatic long-term memory in default community support mode until policies exist.
- Add product-specific docs to template docs.

Exit criteria:

- Fresh clone runs API and migrations.
- Secret scan clean.
- Baseline tests pass.
- Known risky defaults are documented and controlled.

## Phase 1: Tenant Control Plane

Goal: create tenant SaaS spine.

Deliverables:

- `tenants`, memberships/roles, tenant config/version.
- Tenant-aware auth dependencies.
- Admin/operator APIs for tenant lifecycle.
- Audit events for config mutation.
- RLS or equivalent isolation decision implemented for first tenant tables.

Exit criteria:

- Tenant A cannot read/write Tenant B data.
- Config mutations audited.
- Disabled tenant cannot be used for runtime.
- Migration upgrade/downgrade passes.

## Phase 2: Platform Ingest And Delivery

Goal: create trusted runtime event path.

Deliverables:

- Adapter credential/principal model.
- Tenant platform mapping.
- Normalized inbound event endpoint.
- Chat events and idempotency.
- Outbound delivery envelope and delivery record.
- Telegram sandbox adapter.

Exit criteria:

- Telegram message resolves tenant and persists trusted event.
- Duplicate platform message is idempotent.
- Adapter cannot supply trusted tenant id.
- Outbound delivery is idempotent.
- Unknown mapping fails closed.

## Phase 3: Agent Runtime Skeleton

Goal: replace generic chat loop with replayable domain graph.

Deliverables:

- AgentState.
- Graph nodes: hydrate, classify, risk, route, policy, response, emit, record.
- Agent run/step records.
- Mock model/tool interfaces.
- Safe fallback and shadow behavior.
- Replay tests.

Exit criteria:

- Saved trusted event replays with mocked outputs.
- Tenant id immutable.
- No real LLM in unit tests.
- Outbound only after policy check.
- Run/step records created.

## Phase 4: Knowledge And RAG

Goal: answer from approved tenant knowledge.

Deliverables:

- Knowledge source/version/document/chunk/sync job model.
- One source type first, preferably uploaded Markdown or URL allowlist.
- Deterministic parser/chunker.
- VectorSearchProvider contract.
- pgvector or Qdrant implementation behind provider.
- `rag.search` built-in capability.
- Citation builder and refusal policy.

Exit criteria:

- Tenant A cannot retrieve Tenant B chunks.
- Empty/stale/low-confidence retrieval refuses/escalates.
- Source update/delete/tombstone hides old chunks.
- Source version activation prevents partial sync visibility.

## Phase 5: Capability Registry And Tools

Goal: make tools safe and tenant-configurable.

Deliverables:

- Capability manifest schema.
- Tenant capability enablement.
- Tool proxy.
- Tool audit records.
- Secret handle model.
- Disabled/missing/invalid/timeout tests.
- Built-in `rag.search`; add `crypto.price` only if credentials/rate limits are ready.

Exit criteria:

- Disabled tool cannot execute.
- Tool input/output schemas enforced.
- Tool denials audited.
- Secrets absent from logs/traces/config.

## Phase 6: Moderation Enforcement And Review

Goal: move from risk detection to controlled action.

Deliverables:

- Policy matrix by category/action.
- Review queue.
- Shadow/propose/enforce modes.
- Platform moderation action tools.
- Idempotency and rollback/remediation notes.
- False positive/negative regression set.

Exit criteria:

- Shadow/propose/enforce modes behave as configured.
- Destructive actions audited and idempotent.
- Review override works.
- No model text executes destructive action directly.

## Phase 7: Discord, Ops, Reports, And Dashboard

Goal: expand operations after Telegram path is safe.

Deliverables:

- Discord adapter.
- Trace/run inspection APIs.
- Sync retry APIs.
- Reports and scheduled summaries.
- Cost/latency dashboards.
- Operator runbooks.

Exit criteria:

- Discord reuses normalized contracts.
- Operator can debug bad answer from trace to sources/tools/actions.
- Dashboard/API supports core admin operations without DB access.

## Validation Matrix

| Area | Gate |
| --- | --- |
| Code quality | ruff, pyright/mypy-equivalent, pytest. |
| Migrations | Alembic upgrade and downgrade/rollback. |
| Secrets | detect-secrets or project secret scan. |
| Tenant DB | Cross-tenant denial with least privilege. |
| Vector | Cross-tenant and visibility denial. |
| Adapter | Invalid credential, scope mismatch, duplicate message. |
| Graph | replay deterministic with mocked model/tool. |
| Tools | disabled/missing/invalid/timeout/credential failure. |
| Moderation | shadow/propose/enforce policy fixtures. |
| Observability | redaction tests and trace/log sampling policy. |
| Eval | product eval threshold for support/moderation/tool safety. |

## Suggested Local Commands

Start from template commands, then add product gates as they exist:

```bash
make install
make docker-up
make migrate
pytest
ruff check .
pyright app evals
make eval-quick
detect-secrets scan --baseline .secrets.baseline
```

When schema changes:

```bash
make migration MSG="describe change"
make migrate
make migrate-downgrade
make migrate
```

If command names change, update this doc and CI together.

## Risk Register

| Risk | Mitigation |
| --- | --- |
| Template mem0 stores unsafe community memory | Disable/restrict until memory governance exists. |
| SQLModel + RLS friction | Decide isolation pattern early; keep Alembic raw SQL for policies. |
| Generic chat graph ships as product | Replace with domain graph before tenant rollout. |
| Web search hallucination | Disable by default; enable only as policy-controlled tool. |
| Vector backend churn | Define provider contract before pgvector/Qdrant decision. |
| Overbuilding plugins | Start with built-in capabilities and audit. |
| Moderation harm | Shadow/propose first; enforcement after review UX. |
| Trace data leakage | Redaction/sampling before production traces. |

## Completion Checklist For Rebuild Docs

- Product mission and non-goals are clear.
- Tenant model and trusted context are explicit.
- Template features and gaps are separated.
- Persistence and isolation requirements are stated.
- Agent graph and tool boundary are defined.
- Adapter contracts are defined.
- Observability/eval/runbooks are defined.
- Roadmap has phases and exit criteria.
- No dependency on a non-template repository path or module name.
- Docs can be copied into the template and used as source of truth.

## Open Questions Before Implementation

1. Will v1 use pgvector only or add Qdrant behind provider contract?
2. Which tenant admin auth model ships first?
3. What is the first knowledge source type?
4. Which production secret manager is accepted?
5. Which trace backend/data residency model is allowed?
6. What review UI is required before moderation enforcement?
7. Is Discord required before RAG, or after Telegram support is safe?
