# Project Brief

## Mục đích

Định nghĩa lý do tồn tại, phạm vi sản phẩm, nguyên tắc thiết kế, và tiêu chí thành công của Agent Support khi rebuild trên nền FastAPI + LangGraph template.

## Đối tượng đọc

Founder, product owner, engineering lead, backend engineer, AI engineer, security reviewer, operator.

## Tóm tắt

Agent Support là nền tảng vận hành cộng đồng crypto cho **nhiều tenant** (multi-tenant SaaS). Sản phẩm trả lời câu hỏi support, hỗ trợ onboarding, phát hiện rủi ro scam/phishing/toxic, quản lý tri thức chính thức của từng dự án, và lưu audit trail cho mọi hành vi agent/tool/moderation.

Đây không phải chatbot builder tổng quát. Agent Support ưu tiên tenant isolation, auditability, replayability, security, observability, và kiểm soát tool/capability hơn tốc độ demo.

## Mission

Giúp các dự án crypto vận hành cộng đồng Telegram và Discord an toàn hơn, nhất quán hơn, kiểm chứng được hơn bằng agent workflow có kiểm soát.

Ba việc đồng thời:

- Trả lời thành viên bằng thông tin chính thức, có nguồn, biết từ chối khi thiếu bằng chứng.
- Phát hiện hành vi rủi ro (scam link, impersonation, toxic, spam, phishing) trước khi lan rộng.
- Cho operator replay một quyết định agent từ event đầu vào → context → policy → retrieval → tool call → outbound action.

## Product Positioning

Agent Support là "community operations control plane with agents", không phải "chatbot có vài tool".

Khác biệt chính:

- **Multi-tenant by design:** mỗi tenant có config, tri thức, policy, tool, quota, trace, audit riêng. Isolation enforce ở DB layer bằng PostgreSQL RLS (ADR-002).
- **Agent workflow có state và replay:** mỗi run có trace, policy version, model version, tool version, kết quả kiểm soát.
- **Knowledge source có provenance:** câu trả lời dựa trên nguồn tenant-approved hoặc tool được bật rõ ràng.
- **Moderation không để LLM tự ý hành động destructive:** shadow/propose/enforce theo tenant policy.
- **Tool/plugin capability fail closed:** disabled, unknown, thiếu credential, quá budget, invalid schema đều bị từ chối và audit.

## Core Use Cases

### Support Q&A
Thành viên hỏi tokenomics, roadmap, vesting, listing, campaign, staking, bridge, contract address, hướng dẫn sản phẩm. Agent trả lời từ nguồn tenant-approved kèm citation, từ chối/escalate khi retrieval yếu hoặc nguồn stale.

### Scam And Risk Detection
Agent phân loại message có link lạ, impersonation, private DM lure, fake airdrop, wallet-drain phrase, toxic, spam. Default mode shadow hoặc propose; enforce chỉ bật theo policy rõ ràng.

### Onboarding
Agent chào thành viên mới bằng template tenant-specific, official links, safety warnings, rule summary. Deterministic-first, không cần agent tự do nếu template/policy đủ.

### Knowledge Sync
Admin upload/kết nối nguồn chính thức. Hệ thống parse → normalize → chunk → embed → verify → activate source version, chỉ phục vụ bản active đã qua kiểm tra. V1 source type = Markdown upload (ADR liên quan ở roadmap Phase 4).

### Tool And Plugin Operations
Tenant bật/tắt capability (`rag.search`, `crypto.price`, reporting, MCP tương lai). Tool execution schema-validated, timeout-bound, rate/budget-bound, credential-scoped, redacted, audited.

### Audit And Incident Review
Operator nhập trace id / run id để xem event đầu vào, graph steps, retrieval context, tool attempts, moderation decision, outbound result, latency, cost, error summary đã redacted.

## Product Principles

Chi tiết ở [principles.md](principles.md). Tóm tắt 7 nguyên tắc:

1. Tenant boundary trước feature polish.
2. Audit/replay trước automation mạnh.
3. Official source trước confident answer.
4. Policy gate trước outbound hoặc destructive action.
5. Capability manifest trước tool exposure.
6. Trace/redaction trước observability export.
7. Small vertical slices trước platform abstraction.

## Non-Goals For V1

- Không wallet signing.
- Không fund movement.
- Không plugin marketplace công khai.
- Không tự động delete/ban mặc định.
- Không đưa raw chat logs vào RAG knowledge mặc định.
- Không để model tự tạo long-term profile/policy/workflow memory.
- Không cho remote tool/MCP server nhận broad platform token.
- Không biến template thành CRM/ticketing đầy đủ ngay từ đầu.

## Success Criteria (MVP)

- Một tenant kết nối được Telegram (per-tenant bot, webhook mode — ADR-009).
- Admin cấu hình persona, official links, moderation mode, knowledge source.
- Agent trả lời câu hỏi cơ bản từ source đã sync với citation hoặc từ chối khi thiếu bằng chứng.
- Moderation shadow mode ghi được decision và risk reason.
- Mọi request/run/tool/action có trace id.
- Tenant A không đọc được data, memory, vector chunks, tool config, hoặc audit của Tenant B.
- Operator replay/điều tra một bad answer bằng durable records, không phụ thuộc duy nhất vào trace SaaS.
- Tool disabled hoặc thiếu credential fail closed và có audit row.

## Constraints Trong Template Mới

Template đã có: FastAPI, LangGraph, JWT auth, session model, Alembic, pgvector-backed memory, Langfuse tracing, Prometheus/Grafana, rate limiting, Docker, eval scaffolding.

Rebuild tận dụng các phần này thay vì port module cũ:

- Dùng routing, settings, middleware, logging, metrics, auth, eval, Docker pattern của template làm nền.
- Mở rộng LangGraph từ chat/tool loop thành domain workflow cho support/moderation/onboarding.
- Dùng Alembic cho schema và RLS SQL.
- **ORM migrate sang SQLAlchemy 2.0 thuần** ở Phase 0 (ADR-004) — không giữ SQLModel cho domain schema.
- pgvector/mem0 coi là capability có sẵn nhưng **không** đồng nhất với curated tenant knowledge RAG.
- **Vector backend = Qdrant** sau `VectorSearchProvider` contract (ADR-001).

## Rebuild North Star

```text
+ trusted tenant context
+ source-backed knowledge
+ replayable graph run
+ capability permission boundary
+ audit-first operations
-- generic chatbot assumptions
-- unchecked autonomous tools
-- raw memory everywhere
-- demo-only platform adapters
```

## References

- [Product Requirements](product-requirements.md)
- [Principles](principles.md)
- [Glossary](glossary.md)
- [Target Architecture](../01-architecture/system-architecture.md)
- [Rebuild Roadmap](../05-roadmap/rebuild-roadmap-and-validation.md)
