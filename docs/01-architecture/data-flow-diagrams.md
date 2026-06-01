# Data Flow Diagrams

Sequence diagrams per use case. Text-based (mermaid-style ascii) để giữ trong git/review dễ.

## 1. Support Message (Telegram → Answer)

```text
Telegram        API(ingest)         Postgres            Worker            Qdrant     LLM      Delivery
  |  webhook update  |                  |                  |                |        |          |
  |----------------->|                  |                  |                |        |          |
  |  verify secret_token                |                  |                |        |          |
  |  validate adapter principal         |                  |                |        |          |
  |  resolve tenant from platform map   |                  |                |        |          |
  |                  |  BEGIN TX        |                  |                |        |          |
  |                  |  INSERT chat_events (idempotency)   |                |        |          |
  |                  |  INSERT processing_outbox(pending)  |                |        |          |
  |                  |  COMMIT          |                  |                |        |          |
  |<-- 200 OK (<500ms)|                 |                  |                |        |          |
  |                  |                  |  SELECT ... FOR UPDATE SKIP LOCKED|        |          |
  |                  |                  |<-----------------|                |        |          |
  |                  |                  |  SET LOCAL app.current_tenant     |        |          |
  |                  |                  |  hydrate config/policy/caps       |        |          |
  |                  |                  |        classify+risk+route        |        |          |
  |                  |                  |        rag.search (proxy) ------->|        |          |
  |                  |                  |        tenant/version/visibility filter    |          |
  |                  |                  |<--- bounded snippets + citations -|        |          |
  |                  |                  |        draft answer ------------->|------->|          |
  |                  |                  |<--- answer -----------------------|--------|          |
  |                  |                  |  policy_check + citation check    |        |          |
  |                  |                  |  INSERT delivery_outbox + agent_runs/steps |          |
  |                  |                  |                  |                |        | consume  |
  |                  |                  |                  |                |        |<---------|
  |<------------------------ sendMessage -------------------------------------------+          |
  |                  |                  |  INSERT delivery_receipts                 |          |
```

Idempotency: duplicate update → INSERT chat_events fails on UNIQUE → return 200 với existing event_id, no duplicate run.

## 2. Moderation (Shadow / Propose / Enforce)

```text
inbound message -> risk_screen -> classify category/confidence
-> load tenant policy_matrix(category)
   |
   |-- mode=shadow  -> INSERT moderation_decisions(shadow); no outbound.
   |
   |-- mode=propose -> INSERT moderation_decisions(propose)
   |                   -> delivery to tenant.review_chat_id (Telegram inline keyboard)
   |                      [Approve] [Reject] [Escalate]
   |                   -> admin tap -> callback_data{decision_id, action, hmac}
   |                   -> /v1/internal/moderation/callback
   |                   -> verify hmac + role (tenant_memberships)
   |                   -> execute action -> moderation_actions(idempotency_key)
   |                   -> platform API (delete/ban/mute) -> audit
   |
   |-- mode=enforce  -> only if policy explicit per category/action
                        -> moderation_actions(idempotency_key) -> platform API -> audit
```

No destructive action từ raw model text. Review UI Phase 6 = Telegram bot.

## 3. Knowledge Sync (Markdown Upload, Phase 4)

```text
admin upload .md/.zip
-> store raw blob (object storage / bytea)
-> INSERT knowledge_source_versions(status=parsing)
-> parser: split by header -> documents -> chunks (500 tokens, overlap 50)
-> assign citation metadata (source_id, version_id, doc_id, section_path, chunk_id)
-> embed (OpenAI/Anthropic) -> vector
-> upsert Qdrant payload {tenant_id, source_id, version_id, visibility, active, ...}
-> verify: sample query retrieve OK
-> UPDATE source_version status=active
-> rag.search capability serves active version
-> tombstone old version (keep vectors 30d for rollback)
```

Failure → status stays parsing/verifying; partial sync never visible. Sync job records counts + redacted error.

## 4. Tenant Onboarding (Admin Setup)

```text
user signup/login (JWT)
-> create tenant (status=active) + tenant_memberships(user, tenant, role=admin)
-> tenant_config_versions v1 (persona, official_links, moderation_mode, model_budget)
-> Telegram setup: BotFather token -> KMS encrypt -> tenant_platforms + credential handle
-> setWebhook(secret_token)
-> add bot to group -> my_chat_member event -> confirm channel mapping
-> upload knowledge source (Phase 4)
-> enable capabilities (rag.search default; crypto.price opt-in)
-> audit_events for every mutation (actor, trace_id, before/after, config_version)
```

## 5. Incident Replay (Operator)

```text
operator input: trace_id | platform message_id | agent_run_id
-> operator role (BYPASSRLS) + audit access
-> load chat_events + agent_runs + agent_run_steps
-> load tool_calls + retrieval context summary + moderation records
-> load tenant config/policy/source/tool versions @ run time
-> replay graph với mocked model/tool outputs (deterministic)
-> classify root cause: retrieval | prompt | model | policy | tool | adapter | auth | data
-> patch + add regression fixture
-> record incident note + operator actions (audit_events)
```

## 6. Secret Resolution (KMS Envelope, ADR-006)

```text
tool needs credential
-> capability proxy resolve tenant_credential_handles(tenant_id, capability_id)
-> read {ciphertext, dek_handle}
-> KMSProvider.decrypt(dek_handle) -> DEK (in-memory)
-> decrypt(ciphertext, DEK) -> raw secret (in-memory, short-lived)
-> use in tool call
-> discard (no cache long, no log)
```

Production: KMSProvider = CloudKMSProvider (GCP). Pre-flight fail-closed nếu detect LocalKMSProvider.

## References

- [System Architecture](system-architecture.md)
- [Core Agent Design](core-agent-design.md)
- [Adapters And Integrations](adapters-and-integrations.md)
- [Runbooks](../04-observability/runbooks.md)
