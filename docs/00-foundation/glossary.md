# Glossary

Khóa thuật ngữ cho Agent Support. Dùng đúng term này trong code, docs, audit, log.

## Domain Terms

| Term | Meaning |
| --- | --- |
| **Tenant** | Một crypto project/customer dùng platform. Đơn vị isolation cao nhất. |
| **Platform** | Telegram hoặc Discord (Discord defer Phase 7). |
| **Tenant platform** | Mapping giữa tenant và workspace/channel/guild/chat external. |
| **Adapter** | Thin translator giữa platform và internal ingest API. Không own policy/secret/RAG. |
| **Adapter principal** | Credential identity của adapter, scope theo platform/workspace/channel. |
| **Chat event** | Inbound/outbound message event đã chuẩn hóa và gắn tenant. |
| **Trusted event** | Chat event sau khi backend resolve tenant (chỉ event này vào graph). |
| **Agent run** | Một lần graph xử lý một trusted inbound event. |
| **Agent run step** | Một node execution trong một agent run (node name, status, latency, redacted summary). |
| **Knowledge source** | Nguồn official/approved dùng cho RAG (v1 = Markdown upload). |
| **Source version** | Snapshot bất biến của một source tại thời điểm sync. |
| **Knowledge chunk** | Đơn vị text đã chunk/embed, có citation metadata. |
| **Candidate knowledge** | Tri thức đề xuất, cần review trước khi vào RAG. |
| **Capability** | Tool, sub-agent, prompt pack, policy pack, hoặc MCP reference có manifest. |
| **Tool call** | Một attempt gọi capability, có input/output/status/audit. |
| **Moderation decision** | Shadow/propose/enforce record cho một risk evaluation. |
| **Moderation action** | Enforcement record (delete/ban/mute/warn) có idempotency key. |
| **Audit event** | Bản ghi durable về mutation hoặc capability/action attempt. |

## Infrastructure Terms

| Term | Meaning |
| --- | --- |
| **RLS** | PostgreSQL Row-Level Security. Cơ chế isolation chính (ADR-002). |
| **SET LOCAL** | Lệnh set tenant context per-transaction (`SET LOCAL app.current_tenant`). |
| **Outbox** | Bảng Postgres lưu work cần xử lý/gửi, đảm bảo exactly-once (ADR-003). |
| **processing_outbox** | Outbox cho graph work (worker pick up). |
| **delivery_outbox** | Outbox cho outbound platform send. |
| **SKIP LOCKED** | `FOR UPDATE SKIP LOCKED` — pattern claim work song song không lock đụng nhau. |
| **VectorSearchProvider** | Contract trừu tượng cho vector backend (impl v1 = Qdrant, ADR-001). |
| **KMSProvider** | Interface cho envelope encryption (impl v1 = GCP Cloud KMS, ADR-006/008). |
| **DEK** | Data Encryption Key — key mã hóa secret, bản thân DEK được KMS master key mã hóa. |
| **credential_handle** | Reference tới secret đã mã hóa, không phải raw secret. |
| **Service principal** | Machine identity (API key) cho automation/CI (ADR-005). |
| **tenant_membership** | Mapping user → tenant + role. |
| **Checkpointer** | LangGraph `AsyncPostgresSaver`, lưu runtime state để resume/replay. |

## Status & Mode Vocabulary

| Term | Values |
| --- | --- |
| Tenant status | `active`, `disabled`, `suspended`, `deleting` |
| Moderation mode | `shadow`, `propose`, `enforce` |
| Source version status | `parsing`, `verifying`, `active`, `tombstoned` |
| Outbox row status | `pending`, `processing`, `done`, `dead_letter` |
| Visibility | `public`, `private`, `internal` |
| Actor type | `user`, `tenant_admin`, `moderator`, `operator`, `adapter`, `worker`, `tool` |

## Anti-Terms (tránh nhầm)

| Đừng nói | Thay bằng |
| --- | --- |
| "memory" chung chung | Chỉ rõ: runtime state / recent conversation / knowledge / profile / audit. |
| "the bot" | per-tenant Telegram bot (mỗi tenant 1 bot). |
| "search" | `rag.search` capability (curated) vs `web.search` (defer, tenant-enabled). |
| "queue" như source of truth | Outbox = durable; queue/transport ≠ audit source. |
| "trace" như compliance record | Trace = observability artifact; audit_events = source of truth. |

## References

- [Domain And Tenant Model](../01-architecture/domain-and-tenant-model.md)
- [Glossary Quickref](../07-onboarding/glossary-quickref.md)
