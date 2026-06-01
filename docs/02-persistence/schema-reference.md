# Schema Reference

Full SQL DDL + index plan cho domain tables. SQLAlchemy 2.0 ORM (ADR-004), RLS enforced (ADR-002). DDL là reference design — Alembic migration là source of truth thực thi.

> Convention: mọi tenant-owned table có `tenant_id UUID NOT NULL` + RLS policy. PK = UUID (`gen_random_uuid()`). Timestamps `timestamptz DEFAULT now()`. RLS SQL pattern: [migration-rules.md](migration-rules.md).

## Extensions & Roles

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid()

-- Least-privileged app role (no BYPASSRLS)
CREATE ROLE app_user WITH LOGIN PASSWORD :'app_pw';
-- Operator role for incident response
CREATE ROLE app_operator WITH LOGIN PASSWORD :'op_pw' BYPASSRLS;
```

## Tenant & Auth

```sql
CREATE TABLE tenants (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug            TEXT UNIQUE NOT NULL,
    display_name    TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active','disabled','suspended','deleting')),
    config_version  INT  NOT NULL DEFAULT 1,
    retention_policy_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);

CREATE TABLE tenant_roles (
    id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name  TEXT UNIQUE NOT NULL          -- admin|moderator|viewer
);

CREATE TABLE tenant_memberships (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id  UUID NOT NULL REFERENCES tenants(id),
    user_id    UUID NOT NULL,           -- template user
    role       TEXT NOT NULL REFERENCES tenant_roles(name),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, user_id)
);

CREATE TABLE service_principals (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID NOT NULL REFERENCES tenants(id),
    name          TEXT NOT NULL,
    key_hash      TEXT NOT NULL,         -- hashed API key, never raw
    scopes        TEXT[] NOT NULL DEFAULT '{}',
    status        TEXT NOT NULL DEFAULT 'active',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_used_at  TIMESTAMPTZ
);

CREATE TABLE tenant_config_versions (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID NOT NULL REFERENCES tenants(id),
    version       INT  NOT NULL,
    persona       JSONB NOT NULL DEFAULT '{}'::jsonb,
    official_links JSONB NOT NULL DEFAULT '[]'::jsonb,
    moderation_mode TEXT NOT NULL DEFAULT 'shadow',
    model_budget  JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, version)
);
CREATE INDEX idx_membership_user ON tenant_memberships(user_id);
CREATE INDEX idx_sp_tenant ON service_principals(tenant_id);
```

## Platform & Messaging

```sql
CREATE TABLE tenant_platforms (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id            UUID NOT NULL REFERENCES tenants(id),
    platform             TEXT NOT NULL,             -- telegram|discord
    external_workspace_id TEXT NOT NULL,            -- bot id / guild id
    bot_credential_handle UUID,                     -- -> tenant_credential_handles
    webhook_secret_hash  TEXT,
    status               TEXT NOT NULL DEFAULT 'active',
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (platform, external_workspace_id)
);

CREATE TABLE adapter_credentials (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    platform        TEXT NOT NULL,
    allowed_channel_patterns TEXT[] NOT NULL DEFAULT '{}',
    credential_handle UUID NOT NULL,
    credential_version INT NOT NULL DEFAULT 1,
    status          TEXT NOT NULL DEFAULT 'active',
    last_rotated_at TIMESTAMPTZ
);

CREATE TABLE platform_channels (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL REFERENCES tenants(id),
    platform    TEXT NOT NULL,
    channel_id  TEXT NOT NULL,
    visibility  TEXT NOT NULL DEFAULT 'public',
    UNIQUE (platform, channel_id)
);

CREATE TABLE chat_events (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id            UUID NOT NULL REFERENCES tenants(id),
    trace_id             UUID NOT NULL,
    platform             TEXT NOT NULL,
    channel_id           TEXT NOT NULL,
    thread_id            TEXT,
    direction            TEXT NOT NULL,            -- inbound|outbound
    external_message_id  TEXT NOT NULL,
    user_id_hash         TEXT,
    text_preview         TEXT,
    received_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, platform, external_message_id, direction)
);

CREATE TABLE processing_outbox (
    id           BIGSERIAL PRIMARY KEY,
    tenant_id    UUID NOT NULL REFERENCES tenants(id),
    event_id     UUID NOT NULL REFERENCES chat_events(id),
    status       TEXT NOT NULL DEFAULT 'pending',  -- pending|processing|done|dead_letter
    run_after_ts TIMESTAMPTZ NOT NULL DEFAULT now(),
    worker_id    TEXT,
    heartbeat_at TIMESTAMPTZ,
    retries      INT NOT NULL DEFAULT 0,
    last_error   TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE delivery_outbox (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    agent_run_id    UUID NOT NULL,
    envelope        JSONB NOT NULL,
    idempotency_key TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    retries         INT NOT NULL DEFAULT 0,
    last_error      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, idempotency_key)
);

CREATE TABLE delivery_receipts (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID NOT NULL REFERENCES tenants(id),
    delivery_id   BIGINT NOT NULL REFERENCES delivery_outbox(id),
    platform_response JSONB,
    delivered_at  TIMESTAMPTZ
);

-- Outbox polling index (ADR-003)
CREATE INDEX idx_proc_outbox_claim ON processing_outbox (status, run_after_ts, id)
    WHERE status = 'pending';
CREATE INDEX idx_deliv_outbox_claim ON delivery_outbox (status, id)
    WHERE status = 'pending';
CREATE INDEX idx_chat_events_tenant_trace ON chat_events (tenant_id, trace_id);
```

## Agent Runtime

```sql
CREATE TABLE agent_runs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES tenants(id),
    trace_id            UUID NOT NULL,
    input_event_id      UUID NOT NULL REFERENCES chat_events(id),
    platform            TEXT NOT NULL,
    graph_version       TEXT NOT NULL,
    config_version      INT NOT NULL,
    policy_version      INT NOT NULL,
    intent              TEXT,
    status              TEXT NOT NULL,         -- succeeded|refused|escalated|failed|denied
    latency_ms          INT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE agent_run_steps (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID NOT NULL REFERENCES tenants(id),
    agent_run_id  UUID NOT NULL REFERENCES agent_runs(id),
    node_name     TEXT NOT NULL,
    status        TEXT NOT NULL,
    latency_ms    INT,
    summary       JSONB,                       -- redacted
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE model_calls (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID NOT NULL REFERENCES tenants(id),
    agent_run_id  UUID NOT NULL REFERENCES agent_runs(id),
    provider      TEXT, model TEXT, prompt_version TEXT,
    temperature   NUMERIC, max_tokens INT,
    input_tokens  INT, output_tokens INT, cost_usd NUMERIC,
    timeout_ms    INT, outcome TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Checkpointer metadata wrapper (LangGraph saver owns its own tables;
-- this records tenant_id for RLS-aware filtering, ADR-002)
CREATE TABLE graph_checkpoint_metadata (
    thread_id     TEXT PRIMARY KEY,
    tenant_id     UUID NOT NULL REFERENCES tenants(id),
    agent_run_id  UUID,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_runs_tenant_trace ON agent_runs (tenant_id, trace_id);
CREATE INDEX idx_steps_run ON agent_run_steps (agent_run_id);
```

## Knowledge

```sql
CREATE TABLE knowledge_sources (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL REFERENCES tenants(id),
    name        TEXT NOT NULL,
    source_type TEXT NOT NULL DEFAULT 'markdown',  -- markdown|url|gitbook...
    visibility  TEXT NOT NULL DEFAULT 'public',
    status      TEXT NOT NULL DEFAULT 'active',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE knowledge_source_versions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL REFERENCES tenants(id),
    source_id   UUID NOT NULL REFERENCES knowledge_sources(id),
    version     INT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'parsing',  -- parsing|verifying|active|tombstoned
    raw_blob_ref TEXT,
    content_hash TEXT,
    activated_at TIMESTAMPTZ,
    tombstoned_at TIMESTAMPTZ,
    UNIQUE (source_id, version)
);

CREATE TABLE knowledge_documents (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id         UUID NOT NULL REFERENCES tenants(id),
    source_version_id UUID NOT NULL REFERENCES knowledge_source_versions(id),
    title             TEXT, section_path TEXT[]
);

CREATE TABLE knowledge_chunks (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id         UUID NOT NULL REFERENCES tenants(id),
    source_version_id UUID NOT NULL REFERENCES knowledge_source_versions(id),
    document_id       UUID NOT NULL REFERENCES knowledge_documents(id),
    chunk_index       INT NOT NULL,
    content_hash      TEXT NOT NULL,
    qdrant_point_id   UUID NOT NULL,             -- maps to Qdrant payload
    active            BOOLEAN NOT NULL DEFAULT false
);

CREATE TABLE knowledge_sync_jobs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL REFERENCES tenants(id),
    source_id   UUID NOT NULL REFERENCES knowledge_sources(id),
    status      TEXT NOT NULL,
    counts      JSONB, retries INT NOT NULL DEFAULT 0,
    error_code  TEXT, error_summary TEXT,        -- redacted
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE knowledge_candidates (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL REFERENCES tenants(id),
    proposed_text TEXT, status TEXT NOT NULL DEFAULT 'pending_review',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE knowledge_ingest_audit (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL REFERENCES tenants(id),
    source_version_id UUID, action TEXT, detail JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_chunks_active ON knowledge_chunks (tenant_id, source_version_id, active);
```

## Capabilities & Tools

```sql
CREATE TABLE plugin_manifests (
    id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plugin_name TEXT NOT NULL, version TEXT NOT NULL, owner TEXT,
    manifest_json JSONB NOT NULL, UNIQUE (plugin_name, version)
);

CREATE TABLE plugin_capabilities (
    id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    manifest_id UUID NOT NULL REFERENCES plugin_manifests(id),
    name TEXT NOT NULL, type TEXT NOT NULL, risk_level TEXT NOT NULL
);

CREATE TABLE tenant_capability_enablement (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID NOT NULL REFERENCES tenants(id),
    capability_name TEXT NOT NULL, enabled BOOLEAN NOT NULL DEFAULT false,
    UNIQUE (tenant_id, capability_name)
);

CREATE TABLE tenant_tool_policies (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL REFERENCES tenants(id),
    capability_name TEXT NOT NULL,
    timeout_ms INT, budget JSONB, rate_limit JSONB, approval_required BOOLEAN
);

CREATE TABLE tenant_credential_handles (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID NOT NULL REFERENCES tenants(id),
    capability_id TEXT,
    secret_kind   TEXT NOT NULL,            -- bot_token|api_key|...
    ciphertext    BYTEA NOT NULL,           -- secret encrypted by DEK
    dek_handle    TEXT NOT NULL,            -- DEK encrypted by KMS master
    status        TEXT NOT NULL DEFAULT 'active',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_rotated_at TIMESTAMPTZ
);

CREATE TABLE tool_calls (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID NOT NULL REFERENCES tenants(id),
    agent_run_id  UUID NOT NULL REFERENCES agent_runs(id),
    capability_name TEXT NOT NULL, capability_version TEXT,
    status        TEXT NOT NULL,           -- allowed|denied|executed|failed|timeout
    deny_reason   TEXT, latency_ms INT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE sub_agent_invocations (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID NOT NULL REFERENCES tenants(id),
    agent_run_id  UUID NOT NULL REFERENCES agent_runs(id),
    sub_agent_name TEXT NOT NULL, steps INT, status TEXT
);
CREATE INDEX idx_toolcalls_run ON tool_calls (agent_run_id);
```

## Moderation

```sql
CREATE TABLE policy_versions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL REFERENCES tenants(id),
    version     INT NOT NULL, matrix JSONB NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, version)
);

CREATE TABLE moderation_decisions (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID NOT NULL REFERENCES tenants(id),
    trace_id      UUID NOT NULL, agent_run_id UUID,
    platform TEXT, channel_id TEXT, message_id TEXT,
    category TEXT, confidence NUMERIC, detector_version TEXT,
    policy_version INT, mode TEXT NOT NULL,       -- shadow|propose|enforce
    proposed_action TEXT, status TEXT NOT NULL DEFAULT 'pending',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE moderation_actions (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID NOT NULL REFERENCES tenants(id),
    decision_id   UUID NOT NULL REFERENCES moderation_decisions(id),
    action_type   TEXT NOT NULL, idempotency_key TEXT NOT NULL,
    reviewer_id   UUID, platform_response JSONB,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, idempotency_key)
);

CREATE TABLE review_queue_items (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID NOT NULL REFERENCES tenants(id),
    decision_id   UUID REFERENCES moderation_decisions(id),
    kind          TEXT NOT NULL,                  -- moderation|candidate_knowledge
    status        TEXT NOT NULL DEFAULT 'open',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_review_open ON review_queue_items (tenant_id, status, created_at);
```

## Audit

```sql
CREATE TABLE audit_events (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trace_id      UUID,
    tenant_id     UUID,                            -- nullable for operator-global
    actor_type    TEXT NOT NULL,
    actor_id      TEXT NOT NULL,                   -- stable redacted id
    action        TEXT NOT NULL,                   -- stable.action.name
    resource_type TEXT, resource_id TEXT,
    before_summary JSONB, after_summary JSONB,     -- no raw secrets
    redaction_applied BOOLEAN NOT NULL DEFAULT true,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_tenant_time ON audit_events (tenant_id, created_at);
CREATE INDEX idx_audit_trace ON audit_events (trace_id);
```

## Index Plan Summary

| Concern | Index |
| --- | --- |
| Outbox claim | partial index on `(status, run_after_ts, id) WHERE status='pending'` |
| Tenant + trace lookup | `(tenant_id, trace_id)` on chat_events, agent_runs |
| Idempotency | UNIQUE on chat_events + delivery_outbox + moderation_actions |
| Active chunks | `(tenant_id, source_version_id, active)` |
| Audit queries | `(tenant_id, created_at)` + `(trace_id)` |
| Review queue | `(tenant_id, status, created_at)` |

## References

- [Persistence Strategy](persistence-strategy.md)
- [Migration Rules](migration-rules.md)
- [Vector And RAG Storage](vector-and-rag-storage.md)
- [Domain And Tenant Model](../01-architecture/domain-and-tenant-model.md)
