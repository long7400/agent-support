OK. Đi từng bước. Trước khi vào decisions kỹ thuật, mình propose cấu trúc bộ docs/ mới để bạn duyệt — vì cấu trúc này quyết định mọi file sau.

Proposed docs/ structure

docs/
├── README.md                           # Index + reading order
│
├── 00-foundation/
│   ├── project-brief.md                # Mission, scope, non-goals (refined)
│   ├── product-requirements.md         # Personas, features, SLO, PRD-IDs (refined)
│   ├── glossary.md                     # NEW — terminology lock
│   └── principles.md                   # NEW — 7 product principles, design rules
│
├── 01-architecture/
│   ├── system-architecture.md          # Target architecture (refined)
│   ├── domain-and-tenant-model.md      # Domain entities, isolation invariants (refined)
│   ├── core-agent-design.md            # LangGraph nodes, state, replay (refined)
│   ├── adapters-and-integrations.md    # Telegram/Discord/MCP (refined)
│   └── data-flow-diagrams.md           # NEW — sequence diagrams per use case
│
├── 02-persistence/
│   ├── persistence-strategy.md         # Storage choices, isolation model (refined)
│   ├── schema-reference.md             # NEW — full SQL DDL + index plan
│   ├── migration-rules.md              # NEW — Alembic conventions, RLS SQL pattern
│   └── vector-and-rag-storage.md       # NEW — pgvector/Qdrant contract, citation
│
├── 03-security/
│   ├── threat-model.md                 # NEW — STRIDE-style threat catalog
│   ├── security-and-auditability.md    # Controls, audit, secrets (refined)
│   ├── authn-authz.md                  # NEW — JWT + tenant role + adapter principal
│   └── secret-handling.md              # NEW — handle model, secret manager contract
│
├── 04-observability/
│   ├── observability-evaluation-and-operations.md  # (refined)
│   ├── metrics-catalog.md              # NEW — full Prometheus metric list
│   ├── runbooks.md                     # NEW — bad answer, leak, queue, sync failures
│   └── eval-datasets.md                # NEW — product eval matrix
│
├── 05-roadmap/
│   ├── rebuild-roadmap-and-validation.md  # Phase 0-7 (refined)
│   ├── phase-0-template-hardening.md   # NEW — deep design
│   ├── phase-1-tenant-control-plane.md # NEW — deep design
│   ├── phase-2-platform-ingest.md      # NEW — deep design
│   ├── phase-3-agent-runtime.md        # NEW — deep design
│   ├── phase-4-knowledge-rag.md        # NEW — light outline
│   ├── phase-5-capability-tools.md     # NEW — light outline
│   ├── phase-6-moderation.md           # NEW — light outline
│   └── phase-7-discord-ops.md          # NEW — light outline
│
├── 06-decisions/                       # ADR records
│   ├── adr-template.md
│   ├── adr-001-vector-backend.md
│   ├── adr-002-tenant-isolation-model.md
│   ├── adr-003-graph-execution-mode.md
│   ├── adr-004-orm-choice.md
│   ├── adr-005-tenant-auth-model.md
│   ├── adr-006-secret-manager.md
│   ├── adr-007-trace-backend.md
│   ├── adr-008-deployment-target.md
│   └── adr-009-telegram-bot-strategy.md
│
├── 07-onboarding/
│   ├── getting-started.md              # Dev local setup (rewritten)
│   ├── code-standards.md               # (refined from existing)
│   ├── contribution-flow.md            # NEW — branch, PR, review gates
│   └── glossary-quickref.md            # Cheat sheet
│
└── api-reference/                      # Auto-or-manual API docs
    ├── admin-api.md
    ├── adapter-ingest-api.md
    └── operator-api.md

Principle: numbered folders = reading order. Mỗi doc <= 800 LOC (theo docs.maxLoc config). Cross-refs dùng relative path.

13 decisions sẽ resolve qua ADRs (theo thứ tự foundational → operational):
1. Vector backend
2. Tenant isolation model
3. Graph execution mode (sync vs worker)
4. ORM choice (SQLModel keep vs SQLAlchemy)
5. Tenant admin auth
6. Secret manager
7. Trace backend
8. Deployment target
9. Telegram bot strategy
10. First knowledge source type
11. Discord priority
12. Moderation review UI
13. Retention policy (chat, audit, traces)

---
Invalid tool parameters

  Thought for 6s

⏺ User answered Claude's questions:
· Layout docs/ đề xuất ở trên đã OK chưa? Sau bước này mình bắt đầu hỏi từng decision một để resolve open questions. → OK structure trên (Recommended)

  Thought for 8s

Bắt đầu chuỗi decisions. Mình sẽ hỏi từng cái một, theo thứ tự foundational → operational.

Decision 1/13: Vector backend cho RAG

Context: Template đã có pgvector + mem0 sẵn. Docs design yêu cầu VectorSearchProvider contract trừu tượng để không khoá runtime vào backend cụ thể. Câu hỏi: v1 dùng backend nào sau provider contract đó?

Trade-offs ngắn:

┌──────────────────────────────┬────────────────────────────────────────────────────────────┬─────────────────────────────────────────────────────────────────────────────┐
│            Option            │                            Pros                            │                                    Cons                                     │
├──────────────────────────────┼────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────┤
│ pgvector only (v1)           │ Có sẵn template, 1 DB duy nhất, backup/RLS đơn giản, ít    │ Hiệu năng kém khi >1M chunks/tenant. Không có payload index chuyên dụng.    │
│                              │ moving parts. Tenant filter qua SQL WHERE.                 │ Vector ops cạnh tranh CPU với OLTP.                                         │
├──────────────────────────────┼────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────┤
│ Qdrant ngay v1               │ Filter payload nhanh, scale tốt, dedicated ops.            │ Thêm 1 service stateful, backup/restore riêng, tenant isolation phải tự     │
│                              │                                                            │ enforce ở app layer (không có RLS). Overhead với MVP.                       │
├──────────────────────────────┼────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────┤
│ Provider contract + pgvector │ Lock-free runtime, đổi backend không sửa graph. MVP nhanh  │ Phải viết contract đúng từ đầu (input/output schema, filter spec). Ít rủi   │
│  v1, Qdrant later            │ với pgvector, swap khi scale yêu cầu.                      │ ro hơn 2 option trên.                                                       │
└──────────────────────────────┴────────────────────────────────────────────────────────────┴─────────────────────────────────────────────────────────────────────────────┘

Recommendation: Option 3 — provider contract + pgvector cho v1, Qdrant defer.

Lý do: Phase 4 roadmap chưa có tenant production nào. pgvector qua được isolation tests nếu schema có tenant_id, source_version_id, visibility, active columns + index đúng. Khi nào 1 tenant chạm ~500K chunks hoặc query p95 vượt SLO → swap sang Qdrant qua provider, không động graph.

⏺ User answered Claude's questions:
· Vector backend cho RAG ở v1? → Provider contract + Qdrant ngay v1

  Thought for 6s

OK, ADR-001: Qdrant ngay v1 sau provider contract. Note: cần thêm Qdrant vào docker-compose, tenant isolation enforce ở app layer (Qdrant không có RLS), backup/restore riêng. Mình sẽ ghi đầy đủ vào ADR-001 sau.

---
Decision 2/13: Tenant isolation model

Context: PostgreSQL chứa tenant config, chat events, agent runs, knowledge metadata, audit, tools. PRD-002 yêu cầu RLS hoặc equivalent. Template hiện dùng SQLModel với 1 connection user duy nhất, không có RLS.

Trade-offs:

┌───────────────────────────────────────────────────────┬──────────────────────────────────────────────────┬──────────────────────────────────────────────────────────────┐
│                        Option                         │                       Pros                       │                             Cons                             │
├───────────────────────────────────────────────────────┼──────────────────────────────────────────────────┼──────────────────────────────────────────────────────────────┤
│                                                       │ DB-enforced, bắt được mọi query thiếu predicate. │ Phải dùng app role không phải owner. SET LOCAL app.tenant_id │
│ PostgreSQL RLS từ đầu                                 │  Sec reviewer thích. Test cross-tenant denial    │  per request. Friction với SQLModel session. Alembic phải    │
│                                                       │ chạy ở DB level.                                 │ chứa raw SQL policies.                                       │
├───────────────────────────────────────────────────────┼──────────────────────────────────────────────────┼──────────────────────────────────────────────────────────────┤
│ App-layer enforcement (mandatory tenant filter trong  │ Đơn giản, không đụng SQLModel.                   │ 1 query thiếu WHERE tenant_id = ? = leak. Code review gate   │
│ repository)                                           │                                                  │ phải nghiêm. Test denial khó tin.                            │
├───────────────────────────────────────────────────────┼──────────────────────────────────────────────────┼──────────────────────────────────────────────────────────────┤
│ Schema-per-tenant                                     │ Mạnh nhất về isolation.                          │ Overhead migration N tenants, connection pool phức tạp,      │
│                                                       │                                                  │ không scale tốt. Crypto SaaS với 10-100+ tenants không hợp.  │
├───────────────────────────────────────────────────────┼──────────────────────────────────────────────────┼──────────────────────────────────────────────────────────────┤
│ Hybrid: RLS cho hot tables (chat_events, agent_runs,  │ Cân bằng risk vs friction. Phần data path nóng   │ Cần document rõ table nào RLS, table nào không. Test ma trận │
│ knowledge_chunks, audit) + app-layer cho config/admin │ có DB enforcement, phần admin/config ít risk     │  hơi phức tạp.                                               │
│  tables                                               │ hơn.                                             │                                                              │
└───────────────────────────────────────────────────────┴──────────────────────────────────────────────────┴──────────────────────────────────────────────────────────────┘

Recommendation: Option 1 — RLS từ đầu, áp cho tất cả tenant-owned tables.

Lý do: Docs đã ghi "RLS is preferred because it catches missed application predicates" (security-and-auditability.md:75). Risk lớn nhất của Agent Support là cross-tenant leak — sec reviewer là persona quan trọng. RLS friction với SQLModel chấp nhận được nếu pattern set up đúng từ Phase 1: 1 helper with_tenant_context(session, tenant_id) set SET LOCAL app.current_tenant, app role không phải owner, Alembic migrate có sẵn policy template. Schema-per-tenant out vì scale. Hybrid trì hoãn quyết định khó.

⏺ User answered Claude's questions:
· Tenant isolation model trong PostgreSQL? → Tôi đang suy nghĩ có nên bỏ tenant ra ở scope hiện tại. Dự án chạy productions sẽ thêm vào sau vì hiện tại tôi không biết tương không biết cần hay không

  Thought for 16s

Quan trọng. Đây là decision foundational — nó re-shape toàn bộ docs. Mình phải honest với bạn trước khi vote.

Brutal honesty

Nếu bỏ tenant bây giờ → toàn bộ thiết kế hiện tại trong template-rebuild-docs/ phải viết lại, không phải refine:
- tenant_id xoá khỏi mọi schema
- Adapter principal mapping → 1 bot 1 community
- Capability enablement, policy versions, credential handles → đều flatten
- Audit/observability bỏ tenant label
- RAG storage không cần tenant_id filter

Nhưng nếu sau này add lại tenant: phải migrate schema (thêm tenant_id NOT NULL DEFAULT '<single-tenant-uuid>'), refactor mọi service signature, viết lại RLS, viết lại auth — đó là 1 đợt rebuild lớn thứ 2.

Câu hỏi gốc

Trước khi mình đưa option, cần hiểu rõ dự án phục vụ ai:

⏺ User answered Claude's questions:
· Agent Support này thực sự phục vụ ai? → Ngay từ đầu đã multi-tenant SaaS

  Thought for 7s

OK — multi-tenant SaaS từ đầu. Vậy tenant model giữ nguyên, isolation là invariant cốt lõi. Mình tạo task list để track 13 decisions + doc writes.

  Thought for 7s

Multi-tenant SaaS xác nhận → tenant isolation là invariant cốt lõi. Quay lại Decision 2.

Decision 2/13: Tenant isolation model (re-ask)

Recommendation: PostgreSQL RLS toàn diện từ Phase 1.

Lý do: SaaS multi-tenant từ đầu = sec reviewer là persona quan trọng. RLS bắt được mọi query thiếu predicate ở DB level — app-layer enforcement chỉ cần 1 query miss WHERE tenant_id = ? là leak. Setup 1 lần ở Phase 1 (helper with_tenant_context(), app role không phải owner, Alembic raw SQL policies) → mọi phase sau hưởng lợi.

⏺ User answered Claude's questions:
· Tenant isolation model trong PostgreSQL (multi-tenant SaaS context)? → Dùng skill research thêm đi sau đấy gửi về design tốt nhất

  Thought for 7s

Research before voting. Mình spawn researcher song song để tổng hợp best practice 2025-2026 cho multi-tenant PostgreSQL với FastAPI + SQLModel.

⏺ researcher(Research multi-tenant PostgreSQL isolation)

  Thought for 20s, listed 1 directory

⏺ researcher(Resume researcher to write report)
Done (1 tool use · 37.5k tokens · 33s)


  Thought for 10s, listed 1 directory

Report 198 lines, đã có. Đọc và summary cho bạn.

  Thought for 6s, read 1 file

Đọc xong report 198 lines. Tóm tắt cho bạn:

Research Summary — Decision 2

Verdict của researcher: RLS toàn diện + SET LOCAL trong transaction. App-layer filtering không đủ cho SaaS.

Điểm cần biết để quyết:

1. RLS works với SQLAlchemy 2.0 async + asyncpg, nhưng SET LOCAL BẮT BUỘC phải trong async with db.begin() block. Nếu chạy ngoài transaction → leak sang request kế tiếp qua connection pool.
2. pgbouncer caveat: nếu deploy có pgbouncer, phải dùng session-pool mode, không phải transaction-pool mode. Hoặc bỏ pgbouncer cho app role.
3. LangGraph PostgresSaver gotcha: checkpointer dùng cùng connection pool nhưng không tự set tenant context → phải either (a) include tenant_id trong checkpoint metadata + filter app-side, hoặc (b) dùng service role có BYPASSRLS riêng cho checkpoints. Researcher khuyến nghị (a).
4. pgvector + RLS: ANN index vẫn work, planner cost tăng nhẹ. OK với 10-100 tenants. Nhưng dự án mình đã chọn Qdrant ngay v1 → pgvector + RLS không còn là vấn đề. Qdrant là external, tenant filter ở app layer.
5. Operator role cần riêng với BYPASSRLS cho incident response, audit log mọi truy cập.
6. Counter-argument: RLS sai nếu <5 tenants (per-tenant DB đơn giản hơn) hoặc team thiếu PostgreSQL expertise. Cả 2 không áp dụng ở đây.

Trade-off thật của RLS toàn diện:

┌─────────────────────────────────────────────────┬──────────────────────────────────────────────┐
│                       Pro                       │                     Con                      │
├─────────────────────────────────────────────────┼──────────────────────────────────────────────┤
│ DB-enforced, miss query = denied chứ không leak │ Mọi request phải mở transaction, set context │
├─────────────────────────────────────────────────┼──────────────────────────────────────────────┤
│ Sec reviewer + compliance OK                    │ LangGraph checkpointer cần handle riêng      │
├─────────────────────────────────────────────────┼──────────────────────────────────────────────┤
│ Test cross-tenant denial chạy ở DB level        │ pgbouncer mode constraint                    │
├─────────────────────────────────────────────────┼──────────────────────────────────────────────┤
│ Industry standard (Supabase pattern)            │ Operator query phải qua role riêng + audit   │
└─────────────────────────────────────────────────┴──────────────────────────────────────────────┘

---

⏺ User answered Claude's questions:
· Chốt Decision 2 — tenant isolation model? → RLS toàn diện + SET LOCAL pattern (Researcher recommended)

  Thought for 13s

  Thought for 5s

Decision 4/13: ORM choice — SQLModel vs SQLAlchemy

Context: Template hiện dùng SQLModel (mix Pydantic + SQLAlchemy). Docs data-persistence-and-isolation.md:35-41 để open question. Quyết định này ảnh hưởng mọi schema/repository code Phase 1+.

Trade-offs:

┌────────────────────────────────────────────┬───────────────────────────────────────────────────┬────────────────────────────────────────────────────────────────────────┐
│                   Option                   │                       Pros                        │                                  Cons                                  │
├────────────────────────────────────────────┼───────────────────────────────────────────────────┼────────────────────────────────────────────────────────────────────────┤
│                                            │ Template-native, ít refactor, 1 model = ORM +     │ SQLModel maintainership chậm, edge case phải fallback SQLAlchemy. RLS  │
│ Giữ SQLModel                               │ Pydantic, fast prototyping.                       │ pattern không có docs chính thức cho SQLModel. Mix Pydantic v2 +       │
│                                            │                                                   │ SQLAlchemy 2.0 vẫn còn rough. Trả ORM object trực tiếp dễ leak field.  │
├────────────────────────────────────────────┼───────────────────────────────────────────────────┼────────────────────────────────────────────────────────────────────────┤
│ Migrate sang SQLAlchemy 2.0 thuần +        │ Mature, full async support, RLS docs rõ ràng.     │ Refactor template auth/session/database modules. Tốn 1-2 tuần Phase 0. │
│ Pydantic v2 riêng                          │ Tách rõ persistence model vs API DTO. Researcher  │  Phải maintain 2 layer (ORM model + Pydantic schema).                  │
│                                            │ report (Decision 2) viết bằng pure SQLAlchemy.    │                                                                        │
├────────────────────────────────────────────┼───────────────────────────────────────────────────┼────────────────────────────────────────────────────────────────────────┤
│ Hybrid: SQLModel cho legacy template       │                                                   │                                                                        │
│ tables (User, Session) + SQLAlchemy 2.0    │ Không động template, domain code clean.           │ 2 ORM pattern trong codebase = học cost, dev confusion.                │
│ cho domain tables mới (tenants,            │                                                   │                                                                        │
│ chat_events, ...)                          │                                                   │                                                                        │
└────────────────────────────────────────────┴───────────────────────────────────────────────────┴────────────────────────────────────────────────────────────────────────┘

Recommendation: Option 2 — migrate sang SQLAlchemy 2.0 thuần ngay Phase 0.

Lý do:
- Decision 2 đã chốt RLS toàn diện. Researcher implementation skeleton viết bằng SQLAlchemy 2.0 async, không phải SQLModel. SQLModel + RLS chưa có pattern production-grade.
- Multi-tenant SaaS có nhiều schema (~15-20 bảng). Mix 2 ORM = nợ kỹ thuật ngay từ đầu.
- Tách persistence model vs API DTO là nguyên tắc data ownership (docs/01-architecture/domain-and-tenant-model.md). SQLModel khuyến khích trộn 2 cái này — anti-pattern cho SaaS.
- data-persistence-and-isolation.md:35-41 đã ghi: "If the team wants pure SQLAlchemy, decide before domain schema work begins. Mixing patterns without a decision will slow the rebuild."
- Phase 0 (template hardening) là đúng thời điểm migrate. Phase 1+ chỉ có 2 file template chạm tới (auth.py + session model). Cost chấp nhận được.

Counter-argument: nếu team Python ít người và muốn ship MVP nhanh trong 2-3 tuần thay vì 4-6 tuần, giữ SQLModel hợp lý hơn. Nhưng compliance + multi-tenant SaaS không phải MVP "ship nhanh".

⏺ User answered Claude's questions:
· Decision 4 — ORM choice cho domain schema? → SQLAlchemy 2.0 thuần + Pydantic v2 riêng (Recommended)

  Thought for 31s

Acknowledged chunked write protocol. Sẽ apply nghiêm khi viết docs (mọi file >300 lines chia chunk).

  Thought for 10s

Decision 5/13: Tenant admin auth model

Context: Template có JWT user + session. Cần thêm cách tenant admin authenticate vào admin API (configure source, policy, tools, persona). Adapter principal đã tách riêng (Decision riêng cho adapter credentials trong adapters-and-integrations.md).

Trade-offs:

┌─────────────────────────────────────────────────┬─────────────────────────────────────────────────────────────┬──────────────────────────────────────────────────────────┐
│                     Option                      │                            Pros                             │                           Cons                           │
├─────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────┼──────────────────────────────────────────────────────────┤
│                                                 │ Reuse template auth. 1 user có thể là admin nhiều tenant    │ Cần build admin UI/CLI để invite members. Session        │
│ JWT user + tenant_memberships table             │ với role khác nhau. Magic link hoặc password reset đơn      │ refresh logic.                                           │
│                                                 │ giản.                                                       │                                                          │
├─────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────┼──────────────────────────────────────────────────────────┤
│                                                 │                                                             │ Không phân biệt actor (audit ghi key id thay vì human).  │
│ API keys per tenant                             │ Đơn giản, không cần UI. CI/CD friendly.                     │ Không có session revoke từng device. Không hợp human     │
│                                                 │                                                             │ admin.                                                   │
├─────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────┼──────────────────────────────────────────────────────────┤
│ JWT user (human) + service principals/API keys  │ Tách rõ human admin vs machine automation. Audit có actor   │ 2 auth path. Cần build cả 2.                             │
│ (automation), kèm tenant_memberships            │ type. CI/CD dùng service principal.                         │                                                          │
├─────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────┼──────────────────────────────────────────────────────────┤
│ OAuth/SSO (Google, GitHub)                      │ Crypto team quen GitHub. Không cần password management.     │ Setup phức tạp, không hợp Phase 1 MVP. Defer.            │
└─────────────────────────────────────────────────┴─────────────────────────────────────────────────────────────┴──────────────────────────────────────────────────────────┘

Recommendation: Option 3 — JWT user + tenant_memberships cho human admin, service principals (API keys) cho automation.

Lý do:
- domain-and-tenant-model.md:55-62 đã list tenant_api_keys or service_principals như đối tượng riêng. Docs đã anticipate.
- Audit actor_type cần phân biệt tenant_admin vs worker vs adapter vs tool (security-and-auditability.md:194). API key only blur biên này.
- MVP Phase 1 chỉ cần: (a) login email/password → JWT, (b) tenant_memberships(user_id, tenant_id, role) lookup, (c) admin tự generate service principal cho automation. OAuth/SSO defer Phase 7.
- Adapter principal đã tách (separate adapter_credentials table), không nhầm với admin auth.

Counter-argument: Nếu tenant team chỉ 1-2 người và lười setup user account, API keys per tenant nhanh hơn. Nhưng audit yêu cầu phân biệt human vs machine → vẫn nên 2 path.

⏺ User answered Claude's questions:
· Decision 5 — tenant admin auth model? → JWT user (human) + service principals (automation) (Recommended)

  Thought for 11s

Acknowledged chunked write protocol — sẽ apply nghiêm khi viết docs.

  Thought for 6s

Acknowledged — sẽ chunk mọi write ≤300 lines.

Decision 3/13: Graph execution mode (sync vs worker)

Context: Khi adapter ingest event, graph có chạy luôn trong HTTP request hay đẩy vào queue cho worker? Quyết định này shape tobaìn bộ Phase 2-3 và deployment topology.

Trade-offs:

┌──────────────────────┬─────────────────────────────────────────────────────────────────────────┬─────────────────────────────────────────────────────────────────────────┐
│        Option        │                                  Pros                                   │                                  Cons                                   │
├──────────────────────┼─────────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────┤
│ Sync trong request   │ Đơn giản: 1 service. Latency thấp khi graph nhanh (<2s). Debug dễ.      │ Adapter timeout nếu graph chậm. Restart server = mất run đang chạy.     │
│ path                 │ Không cần queue infra.                                                  │ Không retry tự động. Không backpressure.                                │
├──────────────────────┼─────────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────┤
│ Async worker +       │ Reliable: chat_event persist → worker pick up. Retry/DLQ. Adapter ACK   │ 2 service (API + worker). Cần outbox pattern hoặc Redis stream/Postgres │
│ outbox               │ ngay. Graph chậm không ảnh hưởng ingest. Scale worker độc lập.          │  listen-notify. Latency tăng (queue lag). Debug khó hơn.                │
├──────────────────────┼─────────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────┤
│ Hybrid: sync với     │ Sync khi <SLO, fallback queue khi over budget.                          │ 2 path = 2 cách fail. Test ma trận phức tạp.                            │
│ fallback worker      │                                                                         │                                                                         │
└──────────────────────┴─────────────────────────────────────────────────────────────────────────┴─────────────────────────────────────────────────────────────────────────┘

SLO target (product-requirements.md): Support p95 ≤ 4s, moderation fast path ≤ 1s, adapter ingest ≤ 500ms excluding graph work. Câu cuối quan trọng — ingest phải < 500ms, graph KHÔNG được nằm trong ingest path nếu muốn đạt SLO này.

Recommendation: Option 2 — async worker + Postgres outbox từ Phase 2.

Lý do:
- SLO adapter ingest p95 ≤ 500ms excluding graph work đã imply tách ingest khỏi graph.
- Telegram webhook timeout ~60s nhưng phải reply nhanh để Telegram không retry. Nếu graph chậm (LLM timeout/retry), webhook fail → Telegram retry → duplicate. Outbox + idempotency giải quyết.
- adapters-and-integrations.md:184-198 đã prefer Pattern B (worker/outbox).
- Outbox pattern không cần Redis/RabbitMQ riêng — dùng PostgreSQL delivery_outbox table + LISTEN/NOTIFY hoặc polling worker. Infra tối thiểu.
- Replay/incident response cần durable event trước graph — worker pattern fit naturally.

Counter-argument: Phase 2-3 MVP có thể dùng sync để ship nhanh, defer worker tới Phase 7. Nhưng rebuild docs nói rõ "PostgreSQL owns durable idempotency. Queue is transport, not audit source" → idempotency vẫn cần outbox pattern dù sync hay async. Đã build outbox thì worker chỉ thêm 1 process consume.

Concretely:
- Adapter POST /v1/adapter/ingest → validate adapter principal → resolve tenant → INSERT chat_events + processing_outbox → 200 OK trả ngay.
- Worker process LISTEN processing_outbox (hoặc polling) → load event → run graph → write agent_runs + delivery_outbox → adapter consume delivery → send platform.

⏺ User answered Claude's questions:
· Decision 3 — graph execution mode? → Research trên mạng và đưa ra phương pháp tốt nhất ( redis, kafka, celery và mọi fw/lib đều được chấp nhận )

  Thought for 7s

Research song song cho Decision 3.

⏺ researcher(Research async graph execution patterns)

  Thought for 15s, listed 1 directory

Researcher không ghi file. Mình tự synthesize trực tiếp dựa trên knowledge — sẽ ghi report ngắn gọn sau khi bạn quyết.

Decision 3 — Synthesis (compact)

Verdict cho stack FastAPI + LangGraph + multi-tenant + SLO ingest <500ms:

Recommendation: PostgreSQL outbox + polling worker với FOR UPDATE SKIP LOCKED.

Tại sao không phải các option khác

┌──────────────────────────────────┬─────────┬──────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│              Option              │ Verdict │                                                  Lý do                                                   │
├──────────────────────────────────┼─────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Celery                           │ ❌      │ Sync-first, async hỗ trợ rough. 2025 vẫn nhiều issue với asyncio + Celery. Overkill.                     │
├──────────────────────────────────┼─────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ arq (Redis)                      │ ⚠️      │ Clean async nhưng split storage (Postgres + Redis). 2-step commit, drift risk với chat_events.           │
├──────────────────────────────────┼─────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Dramatiq                         │ ⚠️      │ Hơn Celery nhưng cùng vấn đề split storage.                                                              │
├──────────────────────────────────┼─────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Kafka + faust                    │ ❌      │ Overkill cho 10-100 tenants. Heavy infra.                                                                │
├──────────────────────────────────┼─────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Temporal                         │ ❌      │ Mạnh nhưng 1 cluster nữa cần ops. Dùng khi >5 workflow chains.                                           │
├──────────────────────────────────┼─────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ LISTEN/NOTIFY                    │ ⚠️      │ Latency thấp nhưng connection limit (~100), cần polling fallback.                                        │
├──────────────────────────────────┼─────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Postgres outbox + polling worker │ ✅      │ Same DB transaction với chat_events → exactly-once. SKIP LOCKED cho horizontal scale. Không infra extra. │
└──────────────────────────────────┴─────────┴──────────────────────────────────────────────────────────────────────────────────────────────────────────┘

Pattern cụ thể

1. Adapter POST /v1/adapter/ingest
2. BEGIN TX
   INSERT chat_events (idempotency_key=tenant_id+platform+message_id)
   INSERT processing_outbox (event_id, status='pending', tenant_id, run_after_ts)
   COMMIT  -- atomic
3. Return 200 OK <500ms
4. Worker loop (asyncio):
   SELECT * FROM processing_outbox
   WHERE status='pending' AND run_after_ts <= now()
   ORDER BY id
   FOR UPDATE SKIP LOCKED LIMIT 10
   → run graph (with AsyncPostgresSaver checkpoint)
   → INSERT delivery_outbox + UPDATE outbox status='done'
5. Adapter sender consumes delivery_outbox → platform send → mark delivered

Critical points

1. Idempotency: chat_events có UNIQUE constraint (tenant_id, platform, external_message_id). Telegram retry duplicate → INSERT fails → return 200 OK với existing event_id.
2. Crash recovery: Worker crash giữa graph → AsyncPostgresSaver checkpoint còn → restart worker pick up cùng event (vẫn status='processing' với worker_id+heartbeat) → resume từ checkpoint. Stale processing rows >timeout → reclaim.
3. Per-tenant fairness: Polling query thêm ORDER BY (tenant_id, id) hoặc partition queue per tier. Không cần Phase 2-3 nếu workload đều.
4. Retry/DLQ: outbox columns retries INT, last_error TEXT, dead_letter BOOL. Worker retry với exponential backoff, sau N lần → dead_letter=true.
5. Migration path: Nếu sau này cần >10K events/sec hoặc multi-region → swap sang Kafka. Outbox abstraction giữ nguyên consumer interface.

Trade-offs honest

- Pros: 1 storage, transactional consistency, infra tối thiểu (chỉ Postgres), debug bằng SQL, RLS-friendly (outbox có tenant_id).
- Cons: Polling latency 1-2s nếu interval 1s (acceptable cho chat, không cho realtime <100ms). DB load tăng nhẹ với 10+ workers polling cùng lúc — mitigate bằng LISTEN/NOTIFY wake-up + polling fallback nếu cần.

Combo "polling + LISTEN/NOTIFY hybrid"

Production-grade: worker LISTEN channel outbox_new, khi NOTIFY → poll ngay; nếu không có NOTIFY 5s → poll fallback. Best of both: low latency + crash safety.
Invalid tool parameters

  Thought for 6s

⏺ User answered Claude's questions:
· Decision 3 — graph execution mode? → Postgres outbox + polling worker (SKIP LOCKED) (Recommended)

  Thought for 9s

Acknowledged chunked write protocol. Sẽ chunk mọi write ≤300 lines.

  Thought for 8s

Decision 6/13: Secret manager

Context: Cần lưu (a) provider API keys (OpenAI, Anthropic), (b) tenant adapter credentials (Telegram bot tokens), (c) tenant tool credentials (crypto.price API keys, MCP server credentials), (d) DB passwords, JWT secret. Docs security-and-auditability.md:96-114 cấm raw secrets trong config/prompt/log/trace; chỉ cho phép credential_handle references.

Trade-offs:

┌────────────────────────────────────────┬──────────────────────────────────────────────────────────────────────────────┬─────────────────────────────────────────────────┐
│                 Option                 │                                     Pros                                     │                      Cons                       │
├────────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────┤
│ HashiCorp Vault                        │ Industry standard, mature, dynamic secrets, audit log built-in,              │ Tự host = ops overhead. Learning curve.         │
│                                        │ lease/renewal.                                                               │ Overkill MVP <100 tenants.                      │
├────────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────┤
│ AWS Secrets Manager / GCP Secret       │                                                                              │ Lock-in cloud provider. Cost mỗi secret         │
│ Manager / Azure Key Vault              │ Managed, IAM integration, rotation built-in, audit log.                      │ ~$0.40/month → 100 tenants × 5 secrets =        │
│                                        │                                                                              │ $200/month.                                     │
├────────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────┤
│ Doppler / Infisical                    │ SaaS, dev-friendly UX, free tier, dynamic env injection.                     │ Less control, vendor lock.                      │
├────────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────┤
│ Postgres tenant_credentials table với  │ Same DB, no extra infra. Encrypted column với pgp_sym_encrypt. Master key    │ Tự build rotation/audit. Master key management  │
│ pgcrypto (encrypted at rest)           │ trong env/KMS. RLS apply như tenant data.                                    │ vẫn cần secret manager. KMS-less version yếu.   │
├────────────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────┤
│ Hybrid: KMS-backed envelope encryption │ Secret material encrypted in DB với DEK, DEK encrypted bởi KMS master key.   │ Setup phức tạp hơn. Nhưng đã có pattern tương   │
│  trong Postgres                        │ Resolve handle → KMS decrypt DEK → decrypt secret. App never sees raw secret │ đối chuẩn.                                      │
│                                        │  cached.                                                                     │                                                 │
└────────────────────────────────────────┴──────────────────────────────────────────────────────────────────────────────┴─────────────────────────────────────────────────┘

Recommendation: Option 5 — KMS envelope encryption + Postgres credential table, deferring choice giữa KMS providers (cloud KMS hoặc HashiCorp Vault Transit) đến Decision 8 (deployment target).

Lý do:
- Multi-tenant 10-100 tenants × 5 secrets = 500 secrets. Cloud Secrets Manager cost không kinh khủng nhưng API call latency cộng dồn cho mỗi tool call → cache layer cần thiết.
- Envelope encryption pattern: master key (KMS) encrypt DEK, DEK encrypt secret, store ciphertext + DEK_handle trong DB. Resolve handle = KMS decrypt DEK in-memory → decrypt secret → use → discard. Không log raw, không cache lâu.
- tenant_credential_handles table có tenant_id → RLS policy. Operator role với BYPASSRLS audit lúc emergency rotate.
- Tránh lock-in: KMS provider behind interface (KMSProvider với encrypt/decrypt methods). v1 dùng cloud KMS theo deployment, có thể swap Vault Transit sau.
- security-and-auditability.md:96-104 cho phép "encrypted credential records with scoped decrypt policy" → fit pattern này.

Phase 1 deliverable:
- tenant_credentials table: id, tenant_id, capability_id, secret_kind, ciphertext, dek_handle, created_at, last_rotated_at, status.
- KMSProvider interface với 2 implementations: LocalKMSProvider (file-based, dev only, hard-coded reject in production) và CloudKMSProvider (chọn theo Decision 8).
- Pre-flight check on startup: production env phải có CloudKMSProvider hoặc Vault, fail closed nếu detect local.

Counter-argument: Nếu chỉ <10 tenants và team không quen KMS, đơn giản dùng pgcrypto pgp_sym_encrypt với master key trong systemd-credentials hoặc Docker secret. Vẫn tốt hơn raw config. Nhưng compliance audit sẽ flag → SaaS muốn enterprise customers thì cần KMS thật từ đầu.

⏺ User answered Claude's questions:
· Decision 6 — secret manager strategy? → KMS envelope encryption + Postgres credential table (Recommended)

  Thought for 11s

Acknowledged — sẽ chunk mọi write ≤300 lines.

  Thought for 8s

Acknowledged chunked write protocol — sẽ chunk mọi write ≤300 lines.

Decision 7/13: Trace backend / data residency

Context: Template tích hợp Langfuse cho LLM tracing. Docs observability-evaluation-and-operations.md:140-156 yêu cầu redaction trước khi export trace, sampling, và "internal audit tables là source of truth chứ không phải trace SaaS". Câu hỏi: production tenant traces được phép gửi đi đâu?

Trade-offs:

┌─────────────────────────────────────────────┬───────────────────────────────────────────────────────┬───────────────────────────────────────────────────────────────────┐
│                   Option                    │                         Pros                          │                               Cons                                │
├─────────────────────────────────────────────┼───────────────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────┤
│ Langfuse Cloud (SaaS)                       │ Zero ops. UI tốt, eval framework tích hợp template    │ Tenant data leave premise. Crypto customer compliance sẽ hỏi.     │
│                                             │ sẵn. Nhanh deploy.                                    │ EU/US data residency phải check. Cost theo trace volume.          │
├─────────────────────────────────────────────┼───────────────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────┤
│ Langfuse self-host (Docker/K8s)             │ Cùng feature như cloud. Data ở lại infra của bạn.     │ Ops cost: 1 service nữa (Langfuse server + Postgres +             │
│                                             │ Compliance dễ hơn.                                    │ Clickhouse). Backup/upgrade.                                      │
├─────────────────────────────────────────────┼───────────────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────┤
│ OpenTelemetry → Tempo/Jaeger self-host      │ Open standard, vendor-neutral. Có thể swap sang bất   │ Mất eval framework của Langfuse (template đã build evals dựa trên │
│                                             │ kỳ backend OTLP-compat. Tempo lightweight.            │  Langfuse traces). Phải tự build eval pipeline.                   │
├─────────────────────────────────────────────┼───────────────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────┤
│ Hybrid: Langfuse self-host primary + OTLP   │ Có cả LLM trace tooling + open standard cho           │ Setup phức tạp hơn.                                               │
│ export option                               │ enterprise tenants muốn export sang APM của họ.       │                                                                   │
├─────────────────────────────────────────────┼───────────────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────┤
│ No external trace backend, durable internal │ Đơn giản nhất, no extra service.                      │ Mất khả năng inspect prompt/model output mid-run. Debug khó. Eval │
│  agent_runs/run_steps only                  │                                                       │  framework template không chạy.                                   │
└─────────────────────────────────────────────┴───────────────────────────────────────────────────────┴───────────────────────────────────────────────────────────────────┘

Recommendation: Option 2 — Langfuse self-host từ Phase 0/1, OTLP export defer Phase 7.

Lý do:
- Crypto customer (tenant) sẽ hỏi data residency. Self-host = control. SaaS = audit headache.
- Template đã build eval framework dựa trên Langfuse traces → giữ value đó. Switch sang OTLP/Tempo phải rebuild eval = waste Phase 0 work.
- Self-host Langfuse v2 chạy được với Docker Compose + Postgres + Clickhouse. Cost ops chấp nhận với 1 instance share giữa tenants (data isolation qua Langfuse project per tenant).
- Redaction policy + sampling apply trước khi gửi sang Langfuse (callback handler tự redact). Internal agent_runs/audit_events vẫn là source of truth → nếu Langfuse bị hỏng/down, replay không bị block.
- OTLP export defer Phase 7: nếu tenant lớn yêu cầu export sang Datadog/New Relic của họ, build OTLP exporter sau.

Critical points cần ghi vào docs:
1. Langfuse projects = 1 project per tenant (isolation). Tenant admin có thể có read-only access vào project của mình (nice-to-have).
2. Redaction layer: custom Langfuse callback wrapper redact secrets/PII trước khi flush. Test redaction là release gate.
3. Sampling rate cấu hình per-tenant: default 100% Phase 0-3 (low volume), sampling 10-20% khi production scale.
4. Langfuse data retention: default 30 days. Compliance retention dài hơn → dump sang object storage hoặc rely vào internal agent_runs.

Counter-argument: Nếu team không có ops capacity cho Langfuse self-host (1 service nữa = 1 thứ phải monitor/upgrade), Langfuse Cloud tier free OK cho MVP. Nhưng phải có exit plan rõ → ADR ghi điều kiện migrate self-host (số tenant >5 hoặc enterprise customer ký).

⏺ User answered Claude's questions:
· Decision 7 — trace backend cho LLM observability? → Langfuse self-host (Recommended)

  Thought for 10s

Acknowledged chunked write protocol — sẽ chunk mọi write ≤300 lines.

  Thought for 5s

Acknowledged. Sẽ chunk mọi write ≤300 lines, append incremental.

Decision 8/13: Deployment target

Context: Phase 0 cần chốt deployment để: (a) chọn cloud KMS provider (Decision 6 phụ thuộc), (b) chốt CI/CD pipeline, (c) network egress controls (security-and-auditability.md đã ghi MCP servers cần egress control), (d) backup/restore strategy.

Trade-offs:

┌──────────────────────────────────────────┬──────────────────────────────────────────────────────────┬────────────────────────────────────────────────────────────────────┐
│                  Option                  │                           Pros                           │                                Cons                                │
├──────────────────────────────────────────┼──────────────────────────────────────────────────────────┼────────────────────────────────────────────────────────────────────┤
│ Single Docker host (VPS)                 │ Đơn giản nhất, cost thấp ($20-50/month), full control.   │ Không HA, manual scale, manual backup, single point of failure.    │
├──────────────────────────────────────────┼──────────────────────────────────────────────────────────┼────────────────────────────────────────────────────────────────────┤
│ GCP Cloud Run + Cloud SQL + Memorystore  │ Managed, auto-scale, IAM tích hợp, Cloud KMS có sẵn.     │ Worker process polling outbox không hợp model serverless (cần min  │
│                                          │ Stateless workers tốt.                                   │ instance >0). Cold start. Cost variable.                           │
├──────────────────────────────────────────┼──────────────────────────────────────────────────────────┼────────────────────────────────────────────────────────────────────┤
│ GKE / EKS / AKS                          │ Full Kubernetes, mature ops. Auto-scale workers, managed │ Setup phức tạp, ops cost cao, overkill cho 10-100 tenants ban đầu. │
│                                          │  Postgres tách riêng.                                    │                                                                    │
├──────────────────────────────────────────┼──────────────────────────────────────────────────────────┼────────────────────────────────────────────────────────────────────┤
│ Fly.io                                   │ Đơn giản hơn K8s, Postgres + Redis managed, regions      │ Smaller ecosystem, less mature than GCP/AWS, KMS cần external      │
│                                          │ distribution dễ. KMS qua secrets.                        │ (Vault Cloud).                                                     │
├──────────────────────────────────────────┼──────────────────────────────────────────────────────────┼────────────────────────────────────────────────────────────────────┤
│ Hetzner / DigitalOcean / Linode + Docker │ Cost thấp, full control, đủ cho 10-100 tenants.          │ Manual ops, KMS phải self-host (Vault) hoặc external API.          │
│  Compose                                 │                                                          │                                                                    │
├──────────────────────────────────────────┼──────────────────────────────────────────────────────────┼────────────────────────────────────────────────────────────────────┤
│ Hybrid: Docker Compose dev/staging +     │ Dev cheap, prod managed.                                 │ 2 deployment topology = 2 thứ phải maintain.                       │
│ Cloud Run/GKE production                 │                                                          │                                                                    │
└──────────────────────────────────────────┴──────────────────────────────────────────────────────────┴────────────────────────────────────────────────────────────────────┘

Recommendation cần thêm context — câu hỏi liên quan đến budget, ops capability, và tenant requirements.

Trước khi recommend, cần hiểu:

⏺ User answered Claude's questions:
· Context deployment của bạn? → Solo/small team, cost-first

  Thought for 10s

Acknowledged chunked write protocol — sẽ chunk ≤300 lines mỗi operation.

Decision 8 — Synthesis cho solo/small + cost-first

Brutal honesty trước: Solo dev + multi-tenant SaaS từ đầu là tension thực sự. SaaS muốn HA + auto-scale + KMS managed, nhưng solo cost-first muốn $50/month. Hai mục tiêu kéo ngược nhau. Để giải quyết: design portable ngay từ đầu (Docker + env-driven config + KMS interface) → MVP chạy trên 1 VPS rẻ, khi có customer trả tiền hoặc tenant thứ 5+ thì lift sang managed services không phải rebuild.

Recommendation

Phase 0-3 MVP: Docker Compose trên 1 VPS (Hetzner CX22 €4-7/month hoặc DO $12-24/month).

Stack production v1:
api          → FastAPI (Docker)
worker       → Outbox consumer (Docker, same image, different command)
postgres     → Self-host trong compose (16+ với pgvector — wait, Qdrant đã chốt nên không cần pgvector extension)
qdrant       → Docker
redis        → Docker (rate limit + cache only, KHÔNG outbox)
langfuse     → Docker (Postgres + Clickhouse riêng cho Langfuse)
caddy/traefik → reverse proxy + Let's Encrypt

KMS: Vì cost-first, không dùng cloud KMS managed. Lựa chọn:
- Option A: Self-host HashiCorp Vault (Docker) chỉ làm transit engine cho envelope encryption. Master key trong Vault, app gọi Vault API decrypt DEK. Vault unsealed lúc startup bằng auto-unseal với cloud KMS tier free (GCP Cloud KMS 20K ops/month free) hoặc manual unseal.
- Option B: GCP Cloud KMS direct (free tier 20K ops/month đủ cho 100 tenants × ~200 ops/month). Không cần Vault, app gọi GCP KMS API trực tiếp qua service account JSON. App vẫn portable nếu wrap qua KMSProvider interface.
- Option C: AWS KMS pay-as-you-go ($1/key/month + $0.03/10K ops). Cost ~$5-10/month tổng.

Recommendation cho cost-first: Option B (GCP Cloud KMS direct) vì free tier đủ MVP và simpler hơn Vault self-host. Service account JSON file lưu ngoài git, mount vào container. Khi ngân sách tăng hoặc compliance khắt khe → swap sang Vault qua interface.

Honest cons

- Single VPS = no HA: server crash = downtime. Acceptable cho MVP, nhưng phải có nightly backup off-site (DO snapshots / Hetzner Storage Box / B2).
- Postgres self-host = backup/restore phải tự lo: pg_dump + cron + B2 hoặc dùng pgbackrest.
- Scale ceiling ~50-200 tenants trên 1 VPS depending on workload. Khi chạm: provision Postgres riêng (Neon/Supabase managed), worker scale qua Docker Swarm hoặc swap sang Fly.io/Cloud Run.
- Langfuse + Clickhouse memory: Langfuse self-host cần ~2-4GB RAM. CX22 có 4GB → tight. Nếu chật → bắt đầu với Langfuse Cloud free tier rồi self-host khi VPS nâng cấp.

Migration trigger ghi vào ADR

Lift sang managed (Cloud Run/GKE/Fly.io) khi 1 trong các điều kiện:
- Số tenant >20 hoặc 1 enterprise customer ký SLA HA.
- Postgres size >50GB hoặc query p95 chạm SLO.
- Compliance audit yêu cầu separation of duties (DB tách app server).
- VPS RAM/CPU thường xuyên >70% capacity.

⏺ User answered Claude's questions:
· Decision 8 — deployment v1? → Single VPS + Docker Compose + GCP KMS free (Recommended)

  Thought for 19s

Acknowledged chunked write protocol — sẽ chunk mọi write ≤300 lines.

  Thought for 5s

Acknowledged — sẽ chunk mọi write ≤300 lines.

Decision 9/13: Telegram bot strategy (per-tenant vs shared)

Context: Mỗi tenant cần kết nối Telegram bot vào community của họ. Câu hỏi: 1 bot dùng chung cho all tenants với mapping, hay mỗi tenant có 1 bot riêng?

Trade-offs:

┌─────────────────────────────────┬────────────────────────────────────────────────────────────────────────┬──────────────────────────────────────────────────────────────┐
│             Option              │                                  Pros                                  │                             Cons                             │
├─────────────────────────────────┼────────────────────────────────────────────────────────────────────────┼──────────────────────────────────────────────────────────────┤
│ 1 bot/tenant (tenant tự tạo     │ Tenant brand riêng (@MyProjectSupportBot). Tenant own bot identity.    │ Tenant phải BotFather setup. Mỗi bot 1 webhook URL hoặc 1    │
│ bot, cung cấp token)            │ Rate limit per bot (Telegram giới hạn ~30 msg/sec/bot). Ít risk        │ long-poll worker. Adapter scale theo số tenant. Ops setup    │
│                                 │ cross-tenant qua Telegram side.                                        │ mỗi tenant.                                                  │
├─────────────────────────────────┼────────────────────────────────────────────────────────────────────────┼──────────────────────────────────────────────────────────────┤
│ 1 shared bot, route theo        │ Setup 1 lần. Bot platform của bạn brand chung (@AgentSupportBot).      │ Brand không tenant-specific. Bot phải resolve tenant từ      │
│ group/channel                   │ Tenant chỉ add bot vào group của họ.                                   │ chat_id (DB lookup mỗi message). Nếu bot ban → all tenants   │
│                                 │                                                                        │ down. Telegram rate limit chung.                             │
├─────────────────────────────────┼────────────────────────────────────────────────────────────────────────┼──────────────────────────────────────────────────────────────┤
│ Hybrid: shared bot cho          │ Linh hoạt. Free tenant onboard nhanh (chỉ add shared bot), paid tenant │                                                              │
│ free/trial tier, per-tenant bot │  có brand riêng.                                                       │ 2 path = 2 setup + 2 monitoring.                             │
│  cho paid tier                  │                                                                        │                                                              │
├─────────────────────────────────┼────────────────────────────────────────────────────────────────────────┼──────────────────────────────────────────────────────────────┤
│ Per-tenant bot bắt buộc,        │ Sạch nhất về isolation. Tenant own bot data (Telegram giữ message      │                                                              │
│ platform nhận token qua admin   │ history theo bot).                                                     │ Onboarding cost cao.                                         │
│ onboarding                      │                                                                        │                                                              │
└─────────────────────────────────┴────────────────────────────────────────────────────────────────────────┴──────────────────────────────────────────────────────────────┘

Recommendation: Option 1 — per-tenant bot, tenant tạo bot và submit token qua admin API.

Lý do:
- Multi-tenant SaaS từ đầu → brand isolation là feature, không phải nice-to-have. Tenant bán project crypto của họ → muốn @MyProjectSupportBot chứ không phải @AgentSupportBot.
- Telegram rate limit per-bot. Shared bot = rate limit chung → 1 tenant spam ảnh hưởng tất cả.
- Bot ban scenario: shared bot bị Telegram ban (do 1 tenant lạm dụng) → toàn bộ platform down. Per-tenant bot = blast radius = 1 tenant.
- Token storage đã có pattern từ Decision 6 (KMS envelope encryption + tenant_credentials). Adapter resolve token at runtime qua credential handle.
- Webhook mode: mỗi tenant có endpoint /v1/webhook/telegram/{tenant_id} với secret token validation. 1 FastAPI service handle tất cả tenants.
- Long-poll mode (sandbox/dev): worker process loop qua active tenants, 1 worker = N bots OK với asyncio. Production khuyến nghị webhook để giảm worker count.

Concrete pattern

Onboarding flow:
1. Tenant admin login → admin API.
2. UI/CLI show step-by-step: chat với @BotFather → /newbot → nhận token.
3. Admin paste token vào form → POST /v1/admin/telegram/setup với {bot_token, ...}.
4. Backend validate token (call getMe) → store ciphertext qua KMSProvider → save handle vào tenant_platforms table.
5. Backend register webhook: setWebhook(url=https://api.your.com/v1/webhook/telegram/{tenant_id}, secret_token=<random>). Secret token verify mỗi inbound.
6. Tenant add bot vào Telegram group/channel của họ → bot tự discover qua my_chat_member event → admin confirm channel mapping.

Fail closed cases:
- Token invalid → reject onboarding, audit log.
- Webhook secret mismatch → 401, audit log.
- chat_id không có trong tenant_platforms mapping → drop event, audit log "unknown channel".
- Bot ban detected (Telegram API error) → mark tenant_platform disabled, alert admin.

Counter-argument: Per-tenant bot tốn onboarding effort. Nếu MVP cần demo 5 phút thì shared bot nhanh hơn. Nhưng SaaS production từ đầu → onboarding 10 phút với BotFather acceptable, exchange for proper isolation.

⏺ User answered Claude's questions:
· Decision 9 — Telegram bot strategy? → Per-tenant bot (Recommended)

  Thought for 9s

Acknowledged chunked write protocol. Mọi write sẽ ≤300 lines, append incremental cho file lớn.

  Thought for 5s

Acknowledged. Tiếp Decision 11.

Decision 11/13: Discord priority

Context: Roadmap có Phase 7 = "Discord, Ops, Reports, Dashboard". Câu hỏi từ docs rebuild-roadmap-and-validation.md:291: "Is Discord required before RAG, or after Telegram support is safe?"

Trade-offs:

┌─────────────────────────────────────┬──────────────────────────────────────────────────────────────┬─────────────────────────────────────────────────────────────────────┐
│               Option                │                             Pros                             │                                Cons                                 │
├─────────────────────────────────────┼──────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
│ Discord defer Phase 7 (sau Telegram │ Telegram path stable trước. Domain graph + RAG + capability  │ Customer crypto thường có Discord trước Telegram (Western           │
│  + RAG + Moderation)                │ đã proven. Discord chỉ là adapter mới reuse contract.        │ audience). Mất tenant nếu Discord là requirement.                   │
├─────────────────────────────────────┼──────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
│ Discord Phase 2 song song Telegram  │ Cover 2 platform sớm. Test adapter abstraction từ ngày 1.    │ 2 adapter dev parallel = double effort lúc rủi ro cao nhất. Discord │
│                                     │                                                              │  gateway intent + permission setup phức tạp hơn Telegram.           │
├─────────────────────────────────────┼──────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
│ Discord Phase 4 (sau ingest path    │ Telegram đã proven adapter contract. RAG chưa critical,      │ RAG bị delay.                                                       │
│ stable, trước/song song RAG)        │ Discord có thể dùng support fallback.                        │                                                                     │
├─────────────────────────────────────┼──────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
│ Discord chỉ khi tenant cụ thể yêu   │ YAGNI: build khi có demand.                                  │ Tenant onboarding miss nếu Discord-first.                           │
│ cầu                                 │                                                              │                                                                     │
└─────────────────────────────────────┴──────────────────────────────────────────────────────────────┴─────────────────────────────────────────────────────────────────────┘

Honest insight: Crypto community 2025-2026 split khoảng 60% Telegram (Asian, Russian, EU emerging) và 40% Discord (Western, NFT, gaming). Defer Discord = miss 40% market.

Nhưng:
- Discord adapter design đã có trong adapters-and-integrations.md (gateway vs interactions, intents, permissions). Docs đủ.
- Implementation Discord ~2-3 tuần (gateway client, message_content_intent enrollment, slash commands). Telegram ~1 tuần.
- Adapter contract đã abstract → Discord không động đến graph/RAG/capability.

Recommendation: Phase 7 (sau Telegram MVP + RAG + Moderation) — defer Discord, NHƯNG:
1. Adapter contract design (AdapterPrincipal, NormalizedInboundEvent, OutboundDeliveryEnvelope) phải Discord-ready từ Phase 2. Test bằng 1 mock Discord adapter để verify contract không bị Telegram-shape leak vào.
2. Acceptance criteria Phase 2: "Adapter contract validated với Telegram + 1 paper-design Discord mock". Tránh Telegram-only assumptions ăn vào contract.
3. Promote Discord lên Phase 5 nếu trong giai đoạn pilot, ≥30% prospects yêu cầu Discord.

Counter-argument: Nếu bạn đã có 1-2 customer pilot xác nhận từ trước và họ chỉ dùng Telegram → defer Phase 7 OK. Nếu chưa biết audience → giữ option promote sớm.

⏺ User answered Claude's questions:
· Decision 11 — Discord priority? → Defer Phase 7, contract Discord-ready từ Phase 2 (Recommended)

  Thought for 10s

Acknowledged chunked write protocol. Mọi write ≤300 lines, append incremental cho file lớn.

  Thought for 5s

Acknowledged. Mọi write ≤300 lines, chunked.

Decision 10/13: First knowledge source type

Context: Phase 4 RAG cần parser/chunker đầu tiên. Docs adapters-and-integrations.md:204-216 đã list:
- Admin-uploaded Markdown/FAQ → first lane
- URL allowlist/docs site → early after URL
- GitBook → later
- Google Drive → later
- Raw chat → never direct

Trade-offs:

┌────────────────────────────────┬─────────────────────────────────────────────────────────────────────────────┬───────────────────────────────────────────────────────────┐
│             Option             │                                    Pros                                     │                           Cons                            │
├────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────┼───────────────────────────────────────────────────────────┤
│ Admin-uploaded Markdown/FAQ    │ Đơn giản nhất. Parser deterministic (markdown lib mature). Tenant control   │ Tenant phải curate manually. Update phải re-upload.       │
│ files                          │ toàn bộ content. Không network fetch policy. Onboarding dễ test.            │                                                           │
├────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────┼───────────────────────────────────────────────────────────┤
│ URL allowlist (fetch & index)  │ Tenant chỉ điểm domain → backend fetch + parse. Auto re-sync.               │ Cần fetch policy, robots.txt, redirect handling,          │
│                                │                                                                             │ JS-rendered content, rate limit. Risk fetch private URL.  │
├────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────┼───────────────────────────────────────────────────────────┤
│ GitBook/docs platform          │ Crypto project hay dùng GitBook. Native API → reliable parsing.             │ Specific to GitBook. Defer.                               │
│ connector                      │                                                                             │                                                           │
├────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────┼───────────────────────────────────────────────────────────┤
│ Hybrid: Markdown upload + URL  │ Cover 2 use case sớm.                                                       │ Double effort.                                            │
│ allowlist Phase 4              │                                                                             │                                                           │
├────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────┼───────────────────────────────────────────────────────────┤
│ Markdown only Phase 4, URL     │ Ship MVP knowledge nhanh, prove pipeline.                                   │ Tenant phải copy-paste docs từ GitBook. Friction.         │
│ Phase 5                        │                                                                             │                                                           │
└────────────────────────────────┴─────────────────────────────────────────────────────────────────────────────┴───────────────────────────────────────────────────────────┘

Recommendation: Markdown upload only Phase 4, URL allowlist Phase 5.

Lý do:
- Phase 4 acceptance criteria yêu cầu: tenant isolation cross-test, source version activation, citation, refusal khi empty/stale. Markdown là path đơn giản nhất để verify TẤT CẢ acceptance này. URL adds fetch failure modes làm phức tạp test surface.
- Markdown parser tự viết deterministic (split by ##, ###, paragraph). Không phụ thuộc external lib nặng. Dễ chunker control: chunk size, overlap, header context preserve.
- URL allowlist Phase 5 sau khi Markdown pipeline đã chạy. URL fetcher chỉ replace step "raw input → markdown intermediate" rồi cùng pipeline. Reuse parser/chunker/embedder/upserter.
- GitBook/Drive defer hết vì:
  - GitBook có API, nhưng auth handle phức tạp.
  - Drive yêu cầu OAuth tenant credential → defer Phase 6+.

Concrete pipeline Phase 4:
admin upload .md/.zip → store raw blob (object storage hoặc bytea)
→ create knowledge_source_version (status=parsing)
→ parser: split by header → documents → chunks (size 500 tokens, overlap 50)
→ chunker assign citation metadata (source_id, version_id, doc_id, section_path, chunk_id)
→ embed via OpenAI/Anthropic → vector
→ upsert to Qdrant với payload (tenant_id, source_id, version_id, visibility, ...)
→ verify: query sample → retrieve có/không có lỗi
→ activate source_version (status=active)
→ rag.search capability available

Visibility mặc định: public (community Q&A). Future: private cho internal docs, internal cho admin-only. Visibility filter trong retrieval contract.

Chunk size + overlap: 500 tokens / 50 overlap là default phổ biến. Configurable per source.

Re-sync strategy: Admin upload file mới → tạo source_version mới → parse/embed → activate → tombstone version cũ. Không xoá vector cũ ngay (rollback safety).

Counter-argument: Nếu tenant target là dự án có sẵn GitBook đầy đủ, Markdown upload là friction thật. Nhưng:
- GitBook export Markdown được — tenant export 1 lần upload OK cho MVP.
- Phase 5 GitBook connector dùng GitBook public API, parse nội bộ thành Markdown intermediate → reuse parser → marginal effort.

⏺ User answered Claude's questions:
· Decision 10 — first knowledge source type? → Markdown upload Phase 4, URL Phase 5 (Recommended)

  Thought for 10s

Acknowledged chunked write protocol. Mọi write ≤300 lines, append incremental.

  Thought for 6s

Acknowledged chunked write protocol — mọi write ≤300 lines, append incremental.

Decision 12/13: Moderation review UI

Context: Phase 6 acceptance criteria: review override works, no model text executes destructive action directly. Cần human-in-loop UI cho moderation propose/enforce. Câu hỏi: review UI bao nhiêu là đủ cho Phase 6?

Trade-offs:

┌──────────────────────────────────────────────────────────────┬─────────────────────────────────────────────────────────────┬─────────────────────────────────────────────┐
│                            Option                            │                            Pros                             │                    Cons                     │
├──────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────┼─────────────────────────────────────────────┤
│ Admin web UI đầy đủ (queue list, message context,            │ UX tốt, moderator dùng được.                                │ Dev effort lớn (frontend SPA + auth +       │
│ approve/reject, audit log)                                   │                                                             │ state). 2-4 tuần. Phase 6 bị delay.         │
├──────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────┼─────────────────────────────────────────────┤
│ CLI / API only (operator dùng curl hoặc script)              │ Backend-only effort. Ship Phase 6 nhanh.                    │ Không scalable cho moderator non-technical. │
│                                                              │                                                             │  Risky if customer cần demo UI.             │
├──────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────┼─────────────────────────────────────────────┤
│ Telegram bot review channel (bot post propose action vào     │ Reuse Telegram infra đã có. Native cho audience crypto.     │ Format limited. Risky nếu bot bị ban. Cần   │
│ private admin chat, admin reply /approve /reject)            │ Moderator dùng Telegram quen thuộc. Async friendly.         │ auth verify reply từ admin.                 │
├──────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────┼─────────────────────────────────────────────┤
│ Hybrid: Telegram bot review Phase 6 + web UI Phase 7+        │ Ship Phase 6 nhanh. Web UI khi customer yêu cầu enterprise. │ 2 path → migration cost.                    │
├──────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────┼─────────────────────────────────────────────┤
│ Discord/Slack webhook to existing tenant ops channel         │ Tenant đã có ops channel. Webhook integration nhẹ.          │ Discord chưa support v1 (Decision 11 defer  │
│                                                              │                                                             │ Phase 7). Slack ngoài scope.                │
└──────────────────────────────────────────────────────────────┴─────────────────────────────────────────────────────────────┴─────────────────────────────────────────────┘

Recommendation: Option 4 — Telegram bot review channel Phase 6 + minimal admin API + web UI defer Phase 7+.

Lý do:
- Phase 6 acceptance chỉ cần "review override works", không yêu cầu UX polished. Mục tiêu: moderator approve/reject 1 proposal trong <30s, audit ghi đầy đủ.
- Telegram bot review chat tận dụng infra adapter đã có Phase 2. Bot post message với inline keyboard (Telegram native) → tap approve/reject → callback query → backend verify admin user_id qua tenant_memberships → audit + execute.
- Backend API endpoints minimal: GET /v1/admin/moderation/queue, POST /v1/admin/moderation/{id}/decision (approve/reject/escalate). Web UI Phase 7 chỉ là presentation layer trên top.
- Inline keyboard format chuẩn Telegram, không lo HTML escape complex.
- Counter-attack vector: nếu admin Telegram account bị compromise → fake approve. Mitigate: 2FA cho admin login + verify via auth token trong callback data + rate limit approve actions.

Concrete Phase 6 deliverables:

1. moderation_decisions row được tạo bởi graph (mode=propose)
2. Worker post message vào tenant.review_chat_id (admin chat) qua adapter:
   - Show: original message preview, category, confidence, proposed action
   - Inline keyboard: [Approve] [Reject] [Escalate]
3. Admin tap → callback_data = {decision_id, action, signature}
4. Adapter forward callback → /v1/internal/moderation/callback
5. Backend verify:
   - signature HMAC valid
   - user_id maps to tenant_admin/moderator role
   - decision_id status=pending
6. Backend execute action:
   - approve → moderation_actions row + platform API call (delete/ban/...)
   - reject → mark decision dismissed
   - escalate → mark decision needs_review (queue)
7. Audit: who, when, decision, before/after
8. Reply edit message với outcome

Web UI Phase 7+: shadcn/ui table với queue, click row mở modal context, same API. Không build trước Phase 7.

Counter-argument: Nếu enterprise customer yêu cầu web UI ngay Phase 6 (compliance audit cần screenshot UI), Telegram-only không đủ. Lúc đó promote web UI lên Phase 6.5. Nhưng đa số crypto community ops dùng Telegram tiện hơn web.

⏺ User answered Claude's questions:
· Decision 12 — moderation review UI cho Phase 6? → Telegram bot review + minimal API (Recommended)

  Thought for 9s

Acknowledged chunked write protocol. Mọi write ≤300 lines, append incremental cho file lớn.

  Thought for 6s

Acknowledged chunked write protocol. Mọi write ≤300 lines, append incremental cho file lớn.

Decision 13/13: Retention policy

Context: Multi-tenant SaaS = compliance constraint. data-persistence-and-isolation.md:298-304 để open. Retention ảnh hưởng (a) DB cost, (b) compliance audit, (c) GDPR/data deletion request, (d) backup size.

Categories cần policy:

┌────────────────────────────────────┬──────────────────────────────────────────────────────────┬─────────────────────────────────────────────────────────────────────────┐
│                Data                │                    Default retention                     │                                Reasoning                                │
├────────────────────────────────────┼──────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────┤
│ chat_events                        │ 90 days rolling, configurable per-tenant                 │ Đủ cho incident replay, không phình DB. Tenant policy có thể tăng/giảm. │
├────────────────────────────────────┼──────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────┤
│ agent_runs + run_steps             │ 180 days                                                 │ Replay window dài hơn để debug pattern.                                 │
├────────────────────────────────────┼──────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────┤
│ model_calls                        │ 30 days với token usage summary, lifetime aggregate cost │ Detail expire nhanh, summary giữ cho billing.                           │
├────────────────────────────────────┼──────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────┤
│ audit_events                       │ 2 years minimum                                          │ Compliance audit thường yêu cầu 1-7 năm. 2y default, configurable.      │
├────────────────────────────────────┼──────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────┤
│ moderation_decisions/actions       │ 1 year                                                   │ Pattern analysis + dispute window.                                      │
├────────────────────────────────────┼──────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────┤
│ knowledge_chunks (tombstoned)      │ 30 days sau tombstone, sau đó hard delete                │ Rollback safety + storage hygiene.                                      │
├────────────────────────────────────┼──────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────┤
│ langfuse traces                    │ 30 days                                                  │ Sampling đã giảm volume. Internal agent_runs là source of truth.        │
├────────────────────────────────────┼──────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────┤
│ delivery_outbox (status=delivered) │ 7 days                                                   │ Sau khi delivered, archive ra chat_events. Outbox lean.                 │
├────────────────────────────────────┼──────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────┤
│ processing_outbox (status=done)    │ 7 days                                                   │ Same.                                                                   │
└────────────────────────────────────┴──────────────────────────────────────────────────────────┴─────────────────────────────────────────────────────────────────────────┘

Lifecycle automation:

Daily cron job (worker container):
  retention_sweeper:
    - DELETE FROM chat_events WHERE created_at < now() - tenant.chat_retention
    - DELETE FROM agent_run_steps WHERE created_at < now() - tenant.run_retention
    - cascade through FK với agent_runs
    - audit_events: NEVER auto-delete unless explicit operator action
    - tombstoned chunks: DELETE từ Qdrant + DB sau 30 days
    - Vacuum analyze sau bulk delete

GDPR / tenant deletion:

Khi tenant request delete (status=deleting):
1. Stop ingest mới (adapter reject với tenant_inactive).
2. Drain in-flight: outbox finish hoặc move to DLQ.
3. Hard delete: chat_events, agent_runs, agent_run_steps, model_calls, moderation_*, knowledge_chunks, Qdrant collection, Langfuse project, secret credential handles (KMS DEK rotate/revoke).
4. Audit: ghi tenant_deleted event vào audit_events (kept).
5. Tenant row mark deleted với deletion timestamp, không xoá vì FK trong audit.
6. Workflow phải hoàn thành <30 days theo GDPR.

Backup retention:

- pg_dump daily snapshot → B2/Storage Box, giữ 30 daily + 12 monthly.
- Qdrant snapshot tuần một lần.
- Object storage (raw markdown uploads): tenant control retention, default 1 year.

Per-tenant override:

tenants.retention_policy_json column:
{
  "chat_events_days": 90,
  "agent_runs_days": 180,
  "model_calls_detail_days": 30,
  "audit_events_days": 730,
  "moderation_days": 365
}

Floor enforced by platform: audit_events không cho phép <90 days (compliance), chat_events không quá 7 years (DB cost).

Counter-argument: Default 90/180/730 có thể quá conservative cho cost — 1 tenant active có thể tạo 10K chat_events/day → 90 days = 900K rows. Multi 100 tenants = 90M rows trong chat_events table. Cần partitioning? Phase 7 task: declarative partitioning by month. Phase 1-6 single table OK với indexes.

⏺ User answered Claude's questions:
· Decision 13 — retention policy? → Default retention như đề xuất (Recommended)

  Thought for 20s

Acknowledged chunked write protocol — mọi write ≤300 lines, append incremental cho file lớn.

  Thought for 11s

Acknowledged chunked write protocol — mọi write ≤300 lines, append incremental cho file lớn.

All 13 decisions resolved ✅

┌─────┬───────────────────┬──────────────────────────────────────────────────────────────────────────────────┐
│  #  │     Decision      │                                    Resolution                                    │
├─────┼───────────────────┼──────────────────────────────────────────────────────────────────────────────────┤
│ 1   │ Vector backend    │ Qdrant ngay v1 sau VectorSearchProvider contract                                 │
├─────┼───────────────────┼──────────────────────────────────────────────────────────────────────────────────┤
│ 2   │ Tenant isolation  │ PostgreSQL RLS toàn diện + SET LOCAL pattern + operator role BYPASSRLS           │
├─────┼───────────────────┼──────────────────────────────────────────────────────────────────────────────────┤
│ 3   │ Graph execution   │ Postgres outbox + polling worker (FOR UPDATE SKIP LOCKED) + LISTEN/NOTIFY hybrid │
├─────┼───────────────────┼──────────────────────────────────────────────────────────────────────────────────┤
│ 4   │ ORM choice        │ SQLAlchemy 2.0 thuần + Pydantic v2 riêng (migrate template Phase 0)              │
├─────┼───────────────────┼──────────────────────────────────────────────────────────────────────────────────┤
│ 5   │ Tenant auth       │ JWT user (human) + service principals (automation) + tenant_memberships          │
├─────┼───────────────────┼──────────────────────────────────────────────────────────────────────────────────┤
│ 6   │ Secret manager    │ KMS envelope encryption + Postgres credential table (KMSProvider interface)      │
├─────┼───────────────────┼──────────────────────────────────────────────────────────────────────────────────┤
│ 7   │ Trace backend     │ Langfuse self-host (Docker Compose) với redaction callback                       │
├─────┼───────────────────┼──────────────────────────────────────────────────────────────────────────────────┤
│ 8   │ Deployment v1     │ Single VPS + Docker Compose + GCP Cloud KMS free tier + ADR migrate trigger      │
├─────┼───────────────────┼──────────────────────────────────────────────────────────────────────────────────┤
│ 9   │ Telegram strategy │ Per-tenant bot (tenant tạo qua BotFather) + webhook mode                         │
├─────┼───────────────────┼──────────────────────────────────────────────────────────────────────────────────┤
│ 10  │ Knowledge source  │ Markdown upload Phase 4, URL allowlist Phase 5                                   │
├─────┼───────────────────┼──────────────────────────────────────────────────────────────────────────────────┤
│ 11  │ Discord priority  │ Defer Phase 7, contract Discord-ready từ Phase 2 (mock test)                     │
├─────┼───────────────────┼──────────────────────────────────────────────────────────────────────────────────┤
│ 12  │ Moderation UI     │ Telegram bot review + minimal API Phase 6, web UI defer Phase 7+                 │
├─────┼───────────────────┼──────────────────────────────────────────────────────────────────────────────────┤
│ 13  │ Retention         │ Default 90d/180d/30d/2y/1y/30d/7d + per-tenant override + GDPR <30d              │
└─────┴───────────────────┴──────────────────────────────────────────────────────────────────────────────────┘