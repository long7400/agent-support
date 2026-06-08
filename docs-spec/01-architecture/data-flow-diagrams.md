# Data Flow Diagrams

Sequence diagrams per use case. Text-based diagrams are kept in git for review.

## 1. Support Message (Telegram -> Answer)

```mermaid
sequenceDiagram
    participant T as Telegram
    participant API as API ingest
    participant DB as Postgres
    participant W as Worker
    participant LG as LangGraph Durable Runtime
    participant H as create_agent Harness
    participant C as Capability Runtime
    participant Q as Qdrant
    participant D as Delivery Sender

    T->>API: webhook update
    API->>API: verify secret_token and adapter principal
    API->>DB: resolve tenant from platform map
    API->>DB: INSERT chat_events + processing_outbox pending
    API-->>T: 200 OK under ingest SLO
    W->>DB: SELECT processing_outbox FOR UPDATE SKIP LOCKED
    W->>LG: create/resume checkpoint with trusted runtime event
    LG->>H: invoke harness node
    H->>H: middleware stack builds tenant/platform/memory context
    H->>C: rag.search tool call
    C->>C: validate tenant, schema, risk, budget, visibility
    C->>Q: tenant/source/version filtered search
    Q-->>C: bounded snippets + citations
    C-->>H: redacted structured tool result
    H->>H: model/tool loop + policy-checked response
    H-->>LG: response envelope
    LG->>DB: INSERT delivery_outbox + run/step/model/tool audit
    D->>DB: consume delivery_outbox
    D->>T: sendMessage
    D->>DB: INSERT delivery_receipts
```

Idempotency: duplicate update -> `chat_events` unique key returns existing event id and does not create a duplicate run.

## 2. Moderation (Shadow / Propose / Enforce)

```mermaid
flowchart TD
    A[Inbound Message] --> B[create_agent Harness]
    B --> C[RiskPolicyMiddleware]
    C --> D{Tenant moderation mode}
    D -- shadow --> E[Record moderation_decision only]
    D -- propose --> F[Create review_queue_item]
    D -- enforce --> G{Destructive or high risk?}
    G -- yes --> H[HumanApprovalMiddleware<br/>LangGraph interrupt]
    G -- no --> I[CapabilityRuntime.execute<br/>moderation action]
    F --> J[Telegram Review Bot]
    H --> J
    J --> K[Admin Approve / Reject / Escalate]
    K --> L[Verify HMAC + role + pending state]
    L --> M{Approved?}
    M -- yes --> I
    M -- no --> N[Dismiss / Escalate]
    I --> O[moderation_actions<br/>idempotency + audit]
    E --> O
    N --> O
```

No destructive action may execute directly from raw model text. Review UI Phase 6 = Telegram bot + minimal API.

## 3. Knowledge Sync (Markdown Upload, Phase 4)

```mermaid
flowchart LR
    A[Admin Upload .md/.zip] --> B[Raw Source Blob]
    B --> C[knowledge_source_version<br/>status=parsing]
    C --> D[Parser / Chunker<br/>headers, 500 tokens, overlap 50]
    D --> E[Chunks + Citation Metadata]
    E --> F[Embedding Service]
    F --> G[Qdrant Upsert<br/>tenant/source/version/visibility]
    E --> H[Postgres Lineage<br/>source, version, chunk hash]
    G --> I[Verify Sample Query]
    H --> I
    I --> J[Activate Source Version]
    J --> K[rag.search Capability]
    J --> L[Tombstone Old Version<br/>keep vectors 30d]
```

Failure leaves the source version in parsing/verifying state; partial sync is never visible. CocoIndex may later replace the parser/index job with delta-only indexing, but `rag.search` stays the harness-facing capability.

## 4. Memory Retrieval And Writeback

```mermaid
sequenceDiagram
    participant H as create_agent Harness
    participant M as MemoryMiddleware
    participant S as Short Memory Checkpoint
    participant MS as Memory Service
    participant PG as Postgres Metadata
    participant V as Vector Backend

    H->>M: before_agent
    M->>S: load recent thread + rolling summary
    M->>MS: search long-term memory fixtures/records
    MS->>PG: filter by tenant, user_hash, scope, TTL, visibility
    MS->>V: semantic search within allowed ids if enabled
    V-->>MS: candidate hits
    MS-->>M: redacted memory_context
    M-->>H: attach memory_context
    H->>M: after_agent
    M->>MS: write approved bounded facts only
    MS->>PG: source-of-truth record + audit
    MS->>V: upsert embedding if policy allows
```

Short-term memory remains checkpoint-backed. Qdrant is the default long-term memory embedding index if enabled; Turbovec is optional after a backend spike.

## 5. Tenant Onboarding (Admin Setup)

```text
user signup/login (JWT)
-> create tenant (status=active) + tenant_memberships(user, tenant, role=admin)
-> tenant_config_versions v1 (persona, official_links, moderation_mode, model_budget)
-> Telegram setup: BotFather token -> KMS encrypt -> tenant_platforms + credential handle
-> setWebhook(secret_token)
-> add bot to group -> my_chat_member event -> confirm channel mapping
-> upload knowledge source (Phase 4)
-> enable capabilities (rag.search default; other tools opt-in)
-> audit_events for every mutation (actor, trace_id, before/after, config_version)
```

## 6. Incident Replay (Operator)

```text
operator input: trace_id | platform message_id | agent_run_id
-> operator role (BYPASSRLS) + audit access
-> load chat_events + agent_runs + agent_run_steps
-> load middleware sequence + model_calls + tool_calls + retrieval summaries
-> load tenant config/policy/source/capability versions @ run time
-> replay harness with fake model/tool outputs (deterministic)
-> classify root cause: retrieval | prompt | model | policy | capability | adapter | auth | data
-> patch + add regression fixture
-> record incident note + operator actions (audit_events)
```

## 7. Secret Resolution (KMS Envelope, ADR-006)

```text
CapabilityRuntime.execute(tool requiring credential)
-> load capability manifest + tenant enablement
-> load tenant_credential_handle
-> KMS decrypt in service boundary only
-> call provider with timeout
-> redact provider response/error
-> discard plaintext secret
-> audit handle id/version, never secret value
```
