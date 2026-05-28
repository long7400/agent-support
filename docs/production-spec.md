# Production Spec

## Product

Agent Support is a B2B SaaS platform for crypto projects that need 24/7 community support, moderation, onboarding, and knowledge-base answers across Telegram and Discord.

The product is not a general chatbot builder. It is a tenant-isolated community operations platform with agent workflows, tool permissions, auditability, and fast knowledge sync.

## Goals

- Answer project FAQ from trusted tenant knowledge sources.
- Detect scam, phishing, toxic, and suspicious messages before damage spreads.
- Onboard new members with tenant-specific rules and links.
- Let tenants enable or disable tools, skills, and sub-agents without redeploying.
- Keep docs fresh through incremental knowledge sync.
- Provide audit trails for every moderation and tool action.

## Non-Goals

- No autonomous fund movement in v1.
- No direct wallet signing in v1.
- No public plugin marketplace in v1.
- No full CRM or ticketing system in v1.
- No hard dependency on ElizaOS or AgentScope runtime in v1.

## Personas

| Persona | Need |
| --- | --- |
| Project Admin | Configure sources, persona, moderation rules, and enabled tools. |
| Community Manager | Review agent answers, moderation actions, false positives, and sync status. |
| Community Member | Get fast answers and safe onboarding without knowing an AI is involved. |
| Platform Operator | Monitor health, cost, latency, abuse, and tenant isolation. |

## MVP Features

### Smart Support

- Answer tenant questions from indexed docs.
- Include source citations when possible.
- Refuse when evidence is weak or source is missing.
- Escalate to human when confidence is low.

### Scam and Toxic Detection

- Classify links, impersonation, spam, and toxic content.
- Support tenant policy overrides.
- Emit moderation action proposals before destructive action unless tenant enables auto-action.

### Auto Onboarding

- Welcome new members.
- Apply tenant-specific onboarding message template.
- Surface official links and warnings.

### Plug-and-Play Tools

- Tenant can enable tools by config.
- Tool schemas are typed.
- Tool execution is tenant-scoped, rate-limited, logged, and timeout-bounded.

### Knowledge Sync

- Admin can trigger sync per source.
- System tracks source version, sync status, chunk count, and last success.
- Failed syncs produce actionable error state.

## Core Requirements

| ID | Requirement |
| --- | --- |
| PRD-001 | Every request must carry `tenant_id`, `platform`, `channel_id`, `user_id`, and trace id. |
| PRD-002 | Every tenant-owned row must be protected by application checks and PostgreSQL RLS. |
| PRD-003 | RAG retrieval must filter by `tenant_id` and source visibility. |
| PRD-004 | Tool calls must be validated against tenant enabled plugins. |
| PRD-005 | The system must store enough event data to replay an incident. |
| PRD-006 | Moderation auto-actions must be configurable per tenant and per action type. |
| PRD-007 | Sync jobs must be idempotent and resumable. |
| PRD-008 | LLM provider, model, temperature, and budget limits must be tenant-configurable. |

## SLO Targets

| Path | Target |
| --- | --- |
| Chat support p95 | <= 4 seconds for normal RAG answer |
| Moderation p95 | <= 1 second for fast deny/allow classifier |
| Sync visibility | sync status update within 5 seconds |
| Tool timeout | default 10 seconds, configurable lower per tool |
| Availability v1 | 99.5% monthly target |

## Data Classification

| Data | Classification | Handling |
| --- | --- | --- |
| Tenant config | Confidential | PostgreSQL, RLS, audit changes |
| Chat events | Sensitive | retention policy, redact where possible |
| Knowledge chunks | Tenant confidential | Qdrant payload filters, source ACL |
| Tool credentials | Secret | encrypted at rest, never in logs |
| Agent traces | Sensitive | sampled, redacted, access controlled |

## Acceptance Criteria

- A tenant can connect one Telegram or Discord community.
- A tenant can sync one docs source and ask grounded questions.
- A tenant can enable at least one external tool.
- Scam/toxic detection can run in shadow mode and enforcement mode.
- Admin can inspect answer traces, source citations, and moderation actions.
- Automated validation proves tenant A cannot read tenant B metadata or vectors.
