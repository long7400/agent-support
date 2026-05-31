# Project Brief

## Mục đích

Tài liệu này định nghĩa lý do tồn tại, phạm vi sản phẩm, nguyên tắc thiết kế, và tiêu chí thành công của Agent Support khi xây lại trên nền FastAPI + LangGraph template.

## Đối tượng đọc

Founder, product owner, engineering lead, backend engineer, AI engineer, security reviewer, và operator triển khai production.

## Tóm tắt

Agent Support là nền tảng vận hành cộng đồng crypto cho nhiều tenant. Sản phẩm trả lời câu hỏi support, hỗ trợ onboarding, phát hiện rủi ro scam/phishing/toxic, quản lý tri thức chính thức của từng dự án, và lưu audit trail cho mọi hành vi agent/tool/moderation.

Đây không phải chatbot builder tổng quát. Agent Support phải ưu tiên tenant isolation, auditability, replayability, security, observability, và kiểm soát tool/capability hơn tốc độ demo.

## Mission

Giúp các dự án crypto vận hành cộng đồng Telegram và Discord an toàn hơn, nhất quán hơn, và có thể kiểm chứng hơn bằng agent workflow có kiểm soát.

Sản phẩm phải làm được ba việc cùng lúc:

- Trả lời thành viên bằng thông tin chính thức, có nguồn, và biết từ chối khi thiếu bằng chứng.
- Phát hiện hành vi rủi ro như scam link, impersonation, toxic content, spam, và phishing trước khi thiệt hại lan rộng.
- Cho operator xem lại được một quyết định của agent từ event đầu vào, context, policy, retrieval, tool call, đến outbound action.

## Product Positioning

Agent Support là "community operations control plane with agents", không phải "chatbot có vài tool".

Khác biệt chính:

- Multi-tenant by design: mỗi tenant có cấu hình, tri thức, chính sách, tool, quota, trace, audit riêng.
- Agent workflow có state và replay: mỗi run có trace, policy version, model version, tool version, và kết quả kiểm soát.
- Knowledge source có provenance: câu trả lời phải dựa trên nguồn tenant-approved hoặc tool được bật rõ ràng.
- Moderation không được để LLM tự ý hành động destructive: shadow/propose/enforce phải theo tenant policy.
- Tool/plugin capability fail closed: disabled, unknown, thiếu credential, quá budget, hoặc invalid schema đều bị từ chối và audit.

## Core Use Cases

### Support Q&A

Thành viên hỏi về tokenomics, roadmap, vesting, listing, campaign, staking, bridge, contract address, hoặc hướng dẫn sản phẩm. Agent trả lời từ nguồn tenant-approved, kèm citation khi có thể, và từ chối/escalate khi retrieval yếu hoặc nguồn stale.

### Scam And Risk Detection

Agent phân loại message có link lạ, impersonation, private DM lure, fake airdrop, wallet-drain phrase, toxic content, hoặc spam pattern. Default mode là shadow hoặc propose; enforcement chỉ bật theo policy rõ ràng.

### Onboarding

Agent chào thành viên mới bằng template tenant-specific, official links, safety warnings, và rule summary. Onboarding không cần agent tự do nếu template/policy đủ.

### Knowledge Sync

Admin kết nối hoặc upload nguồn chính thức. Hệ thống parse, normalize, chunk, embed, verify, activate source version, và chỉ phục vụ bản active đã qua kiểm tra.

### Tool And Plugin Operations

Tenant bật/tắt capability như `rag.search`, `crypto.price`, reporting, hoặc future MCP integrations. Tool execution phải schema-validated, timeout-bound, rate/budget-bound, credential-scoped, redacted, và audited.

### Audit And Incident Review

Operator nhập trace id hoặc run id để xem event đầu vào, graph steps, retrieval context, tool attempts, moderation decision, outbound result, latency, cost, và error summary đã redacted.

## Product Principles

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
- Không cho remote tool hoặc MCP server nhận broad platform token.
- Không biến template thành CRM/ticketing đầy đủ ngay từ đầu.

## Success Criteria

MVP được coi là đủ tốt khi:

- Một tenant kết nối được Telegram sandbox hoặc production-safe adapter.
- Admin cấu hình tenant persona, official links, moderation mode, và knowledge source.
- Agent trả lời câu hỏi cơ bản từ source đã sync với citation hoặc từ chối khi thiếu bằng chứng.
- Moderation shadow mode ghi được decision và risk reason.
- Mọi request/run/tool/action có trace id.
- Tenant A không đọc được data, memory, vector chunks, tool config, hoặc audit của Tenant B.
- Operator có thể replay hoặc điều tra một bad answer bằng durable records, không phụ thuộc duy nhất vào trace SaaS.
- Tool disabled hoặc thiếu credential fail closed và có audit row.

## Constraints In The New Template

Template đã có FastAPI, LangGraph, JWT auth, session model, Alembic, pgvector-backed memory, Langfuse tracing, Prometheus/Grafana, rate limiting, Docker, and eval scaffolding.

Vì vậy rebuild nên tận dụng các phần này thay vì mang module cũ sang:

- Dùng routing, settings, middleware, logging, metrics, auth, eval, Docker pattern của template làm nền.
- Mở rộng LangGraph từ chat/tool loop thành domain workflow cho support/moderation/onboarding.
- Dùng Alembic của template cho schema và RLS SQL.
- Tạm coi pgvector/mem0 là capability có sẵn nhưng không đồng nhất nó với curated tenant knowledge RAG.
- Nếu dùng Qdrant sau này, đặt sau một `VectorSearchProvider` contract để không khóa runtime vào backend cụ thể.

## Rebuild North Star

Hãy rebuild như một production tenant platform:

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
