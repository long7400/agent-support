# Product Requirements

## Mục đích

Gom yêu cầu sản phẩm, personas, feature scope, acceptance criteria, SLO, behavior policy cho Agent Support trong repo template mới.

## Đối tượng đọc

Product owner, engineering lead, backend engineer, AI engineer, QA, operator, security reviewer.

## Personas

| Persona | Nhu cầu |
| --- | --- |
| Tenant Admin | Cấu hình project, source, policy, tool, adapter, persona, quota. |
| Community Manager | Theo dõi câu trả lời, moderation decision, false positive, sync status, escalation. |
| Community Member | Nhận câu trả lời nhanh, đúng nguồn, onboarding an toàn. |
| Platform Operator | Giám sát latency, cost, abuse, isolation, secret handling, incident replay. |
| Security Reviewer | Kiểm tra tenant boundary, RLS/isolation, tool permission, audit, redaction, compliance. |

> Security Reviewer là persona cao giá trị vì multi-tenant SaaS từ đầu → cross-tenant leak là rủi ro #1.

## MVP Capabilities

### 1. Tenant Setup
Admin tạo tenant, đặt display name, status, persona, official links, default language, moderation mode, model budget, platform connections.

Acceptance:
- Tenant có status `active`, `disabled`, hoặc `suspended`.
- Disabled tenant không được agent process inbound events.
- Tenant config mutations có audit record (actor, trace id, before/after summary, config version).

### 2. Telegram Support Path
Telegram là platform đầu tiên. **Per-tenant bot** (tenant tạo qua BotFather, submit token), **webhook mode** (ADR-009). Adapter chuẩn hóa inbound event, backend resolve tenant từ trusted platform mapping, graph xử lý qua worker, outbound envelope gửi lại adapter.

Acceptance:
- Adapter request body không chứa trusted tenant id.
- Duplicate platform message không tạo duplicate support action.
- Outbound chỉ publish sau policy check.
- Adapter send chỉ ACK sau khi platform send success hoặc sau delivery receipt/idempotency equivalent.

### 3. Discord Later
Discord defer Phase 7 nhưng adapter contract phải Discord-ready từ Phase 2 (ADR-011 không tạo, ghi ở roadmap). Không để Discord gateway-specific shape lan vào domain workflow.

Acceptance:
- Discord adapter là platform translation layer.
- Message content intent, gateway reconnect, guild/channel mapping, permission setup design riêng trước khi implement.
- Phase 2 acceptance: contract validated với Telegram + 1 paper-design Discord mock.

### 4. Support Answers From Knowledge
Agent trả lời từ tenant-approved knowledge sources hoặc tool được tenant bật. Khi thiếu nguồn / stale / low confidence / policy block → refuse, clarify, hoặc escalate.

Acceptance:
- Every answer path có tenant id, trace id, source/version/citation metadata khi source-backed.
- Empty retrieval không sinh confident answer.
- Public channel không dùng private/internal source trừ khi policy cho phép rõ ràng.

### 5. Scam, Toxic, And Risk Detection
Agent đánh giá risk bằng rule checks + optional classifier. Default non-destructive.

Acceptance:
- Shadow mode ghi risk category, confidence, policy mode, recommendation.
- Propose mode tạo moderation proposal, không tự execute.
- Enforce mode chỉ execute khi tenant policy bật theo category/action.
- Delete/ban/mute action idempotent và audited.

### 6. Onboarding
Agent render welcome/rules/official links từ tenant config và approved sources.

Acceptance:
- Welcome content không lấy từ arbitrary chat memory.
- Official links từ tenant config hoặc approved source.
- Locale variant optional nhưng fallback deterministic.

### 7. Knowledge Management
Admin tạo source, trigger sync, xem sync result, deactivate/tombstone source, review candidate knowledge. V1 source type = Markdown upload.

Acceptance:
- Sync job có status, counts, retries, error code, redacted error summary.
- New source version không active cho đến khi chunk/embed/upsert/sample retrieval pass.
- Deleted/tombstoned source không còn retrievable.
- Candidate knowledge cần review; model không tự approve.

### 8. Tool And Plugin Capabilities
Tenant bật capability theo manifest/policy. Tool execution qua proxy kiểm tra schema, permission, timeout, budget, rate limit, credential handle, audit.

Acceptance:
- Unknown tool, disabled plugin, disabled capability, missing credential, invalid input, timeout, output schema invalid, over budget đều fail closed.
- Denied attempts audit mà không gọi underlying tool.
- Tool output bound/redact trước khi vào prompt.

### 9. Observability And Evaluation
Mỗi run có logs, metrics, traces, eval hooks, durable audit/replay record.

Acceptance:
- Logs có trace id, tenant id, component, status, latency, error code.
- Không log secrets, raw tokens, full private docs, full private chat.
- Eval datasets cover support accuracy, hallucination, scam/toxic, disabled tool attempts, stale source, prompt injection.

## Requirement IDs

| ID | Requirement |
| --- | --- |
| PRD-001 | Every inbound event must resolve trusted tenant context before tenant-owned writes or graph execution. |
| PRD-002 | Tenant-owned persistence must enforce isolation using PostgreSQL RLS (ADR-002). |
| PRD-003 | Every graph run must record trace id, tenant id, platform, channel/thread, input event id, graph version, policy/config version, status. |
| PRD-004 | Knowledge retrieval must filter by tenant, active source version, visibility, and policy. |
| PRD-005 | Support answers must cite approved sources when source-backed and refuse/escalate when confidence insufficient. |
| PRD-006 | Moderation enforcement must be tenant-configurable by category/action and default to non-destructive. |
| PRD-007 | Tool calls must pass manifest, tenant enablement, schema, timeout, budget, credential, audit checks. |
| PRD-008 | Secrets must be stored as handles (KMS envelope encryption, ADR-006), never raw in config, traces, logs, prompts. |
| PRD-009 | Runtime memory must be typed by owner, retention, tenant scope, prompt access, audit behavior. |
| PRD-010 | Raw chat, profile facts, moderation evidence, tool outputs, audit logs, secrets must not enter RAG by default. |
| PRD-011 | Operator must debug one bad answer from trace/run records without depending solely on external traces. |
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

> SLO adapter ingest <= 500ms excluding graph work là lý do chốt async worker + outbox (ADR-003): graph KHÔNG nằm trong ingest path.

## Data Classification

| Data | Classification | Handling |
| --- | --- | --- |
| Tenant config/policy | Confidential | Versioned, tenant isolated, audited. |
| Platform message events | Sensitive | Retention policy, redaction, tenant isolation. |
| Knowledge chunks | Tenant confidential | Source/version/citation metadata, tenant filters. |
| Tool credentials | Secret | KMS envelope encryption only. |
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
| Cross-tenant leak | RLS DB isolation (ADR-002), vector filters (app-layer for Qdrant), tests, tenant-scoped credentials. |
| False moderation action | Shadow/propose default, policy matrix, review queue, idempotency. |
| Tool abuse | Capability registry, schema validation, timeout, audit, no token passthrough. |
| Trace privacy leak | Redaction before Langfuse export; durable audit summary internal. |
| Overbuilding agent platform | Telegram support + moderation shadow first; plugins/subagents later. |

## References

- [Project Brief](project-brief.md)
- [Domain And Tenant Model](../01-architecture/domain-and-tenant-model.md)
- [Persistence Strategy](../02-persistence/persistence-strategy.md)
- [Security And Auditability](../03-security/security-and-auditability.md)
- [Rebuild Roadmap](../05-roadmap/rebuild-roadmap-and-validation.md)
