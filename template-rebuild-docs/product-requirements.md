# Product Requirements

## Mục đích

Tài liệu này gom yêu cầu sản phẩm, personas, feature scope, acceptance criteria, SLO, và behavior policy cho Agent Support trong repo template mới.

## Đối tượng đọc

Product owner, engineering lead, backend engineer, AI engineer, QA, operator, và security reviewer.

## Personas

| Persona | Nhu cầu |
| --- | --- |
| Tenant Admin | Cấu hình project, source, policy, tool, adapter, persona, quota. |
| Community Manager | Theo dõi câu trả lời, moderation decision, false positive, sync status, escalation. |
| Community Member | Nhận câu trả lời nhanh, đúng nguồn, và onboarding an toàn. |
| Platform Operator | Giám sát latency, cost, abuse, isolation, secret handling, và incident replay. |
| Security Reviewer | Kiểm tra tenant boundary, RLS/isolation, tool permission, audit, redaction, compliance. |

## MVP Capabilities

### 1. Tenant Setup

Admin tạo tenant, đặt display name, status, persona, official links, default language, moderation mode, model budget, and platform connections.

Acceptance:

- Tenant có status `active`, `disabled`, hoặc `suspended`.
- Disabled tenant không được agent process inbound events.
- Tenant config mutations có audit record với actor, trace id, before/after summary, và config version.

### 2. Telegram Support Path

Telegram là platform đầu tiên vì dễ sandbox hơn. Adapter chuẩn hóa inbound event, backend resolve tenant từ trusted platform mapping, graph xử lý, outbound envelope được gửi lại adapter.

Acceptance:

- Adapter request body không chứa trusted tenant id.
- Duplicate platform message không tạo duplicate support action.
- Outbound chỉ được publish sau policy check.
- Adapter send chỉ ACK sau khi platform send success hoặc sau delivery receipt/idempotency equivalent.

### 3. Discord Later

Discord phải reuse normalized event contract và agent graph. Không để Discord gateway-specific shape lan vào domain workflow.

Acceptance:

- Discord adapter là platform translation layer.
- Message content intent, gateway reconnect, guild/channel mapping, và permission setup được design riêng trước khi implement.

### 4. Support Answers From Knowledge

Agent trả lời từ tenant-approved knowledge sources hoặc từ tool được tenant bật. Khi thiếu nguồn, stale source, low confidence, hoặc policy block, agent phải refuse, clarify, hoặc escalate.

Acceptance:

- Every answer path có tenant id, trace id, source/version/citation metadata khi source-backed.
- Empty retrieval không sinh confident answer.
- Public channel không dùng private/internal source trừ khi policy cho phép rõ ràng.

### 5. Scam, Toxic, And Risk Detection

Agent đánh giá message risk bằng rule checks và optional classifier. Default non-destructive.

Acceptance:

- Shadow mode ghi risk category, confidence, policy mode, và recommendation.
- Propose mode tạo moderation proposal, không tự execute.
- Enforce mode chỉ execute khi tenant policy bật theo category/action.
- Delete/ban/mute action phải idempotent và audited.

### 6. Onboarding

Agent render welcome/rules/official links từ tenant config và approved sources.

Acceptance:

- Welcome content không lấy từ arbitrary chat memory.
- Official links đến từ tenant config hoặc approved source.
- Locale variant optional nhưng phải fallback deterministic.

### 7. Knowledge Management

Admin tạo source, trigger sync, xem sync result, deactivate/tombstone source, và review candidate knowledge.

Acceptance:

- Sync job có status, counts, retries, error code, redacted error summary.
- New source version không active cho đến khi chunk/embed/upsert/sample retrieval pass.
- Deleted/tombstoned source không còn retrievable.
- Candidate knowledge cần review; model không tự approve.

### 8. Tool And Plugin Capabilities

Tenant bật capability theo manifest/policy. Tool execution đi qua proxy kiểm tra schema, permission, timeout, budget, rate limit, credential handle, and audit.

Acceptance:

- Unknown tool, disabled plugin, disabled capability, missing credential, invalid input, timeout, output schema invalid, hoặc over budget đều fail closed.
- Denied attempts được audit mà không gọi underlying tool.
- Tool output được bound/redact trước khi vào prompt.

### 9. Observability And Evaluation

Mỗi run có logs, metrics, traces, eval hooks, và durable audit/replay record.

Acceptance:

- Logs có trace id, tenant id, component, status, latency, error code.
- Không log secrets, raw tokens, full private docs, hoặc full private chat.
- Eval datasets cover support accuracy, hallucination, scam/toxic, disabled tool attempts, stale source, prompt injection.

## Requirement IDs

| ID | Requirement |
| --- | --- |
| PRD-001 | Every inbound event must resolve trusted tenant context before tenant-owned writes or graph execution. |
| PRD-002 | Tenant-owned persistence must enforce tenant isolation using RLS or an equivalent least-privilege DB/session strategy. |
| PRD-003 | Every graph run must record trace id, tenant id, platform, channel/thread, input event id, graph version, policy/config version, and status. |
| PRD-004 | Knowledge retrieval must filter by tenant, active source version, visibility, and policy. |
| PRD-005 | Support answers must cite approved sources when source-backed and refuse/escalate when confidence is insufficient. |
| PRD-006 | Moderation enforcement must be tenant-configurable by category/action and default to non-destructive. |
| PRD-007 | Tool calls must pass manifest, tenant enablement, schema, timeout, budget, credential, and audit checks. |
| PRD-008 | Secrets must be stored as handles or in a secret manager, never raw in plugin config, traces, logs, or prompts. |
| PRD-009 | Runtime memory must be typed by owner, retention, tenant scope, prompt access, and audit behavior. |
| PRD-010 | Raw chat, profile facts, moderation evidence, tool outputs, audit logs, and secrets must not enter RAG by default. |
| PRD-011 | Operator must be able to debug one bad answer from trace/run records without depending solely on external observability traces. |
| PRD-012 | Adapter and admin trust boundaries must be separate. |
| PRD-013 | Production defaults must reject local/dev secrets and demo-only auth shortcuts. |
| PRD-014 | Every new schema/table/vector/tool contract must have validation gates before production enablement. |

## SLO Targets

| Path | Target |
| --- | --- |
| Support normal answer p95 | <= 4 seconds before platform send. |
| Moderation fast path p95 | <= 1 second for rule/classifier decision. |
| Adapter ingest p95 | <= 500 ms excluding graph work. |
| Tool default timeout | <= 10 seconds, lower per tool when possible. |
| Knowledge sync status update | Visible within 5 seconds of state transition. |
| Availability v1 | 99.5% monthly target after production launch. |

## Data Classification

| Data | Classification | Handling |
| --- | --- | --- |
| Tenant config/policy | Confidential | Versioned, tenant isolated, audited. |
| Platform message events | Sensitive | Retention policy, redaction, tenant isolation. |
| Knowledge chunks | Tenant confidential | Source/version/citation metadata and tenant filters. |
| Tool credentials | Secret | Secret manager or encrypted handles only. |
| Agent traces | Sensitive | Redacted, sampled, access controlled. |
| Audit records | Sensitive/compliance | Durable, append-oriented, not prompt context by default. |
| Eval examples | Sensitive if derived from prod | Redacted before use. |

## Out Of Scope Until Later

- Public plugin marketplace.
- Automated wallet actions.
- Financial transaction execution.
- Arbitrary browser/shell tools.
- Runtime-loaded tenant skills without sandbox/version/audit model.
- Destructive moderation default.
- Direct raw web search in normal support path unless tenant explicitly enables it.

## Product Risks

| Risk | Mitigation |
| --- | --- |
| Hallucinated project facts | Source-backed answers, citation checks, refusal policy. |
| Cross-tenant leak | RLS/equivalent DB isolation, vector filters, tests, tenant-scoped credentials. |
| False moderation action | Shadow/propose default, policy matrix, review queue, idempotency. |
| Tool abuse | Capability registry, schema validation, timeout, audit, no token passthrough. |
| Trace privacy leak | Redaction before Langfuse/log export; durable audit summary stays internal. |
| Overbuilding agent platform | Telegram support + moderation shadow first; plugins/subagents later. |
