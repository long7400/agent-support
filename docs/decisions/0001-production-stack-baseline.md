# ADR 0001: Production Stack Baseline

## Status

Accepted.

## Context

The original `spec.md` proposes a layered crypto community agent SaaS using AgentScope-inspired layers, ElizaOS-style plugins, FastAPI, LangGraph, MCP, CocoIndex, LlamaIndex, TurboVec, Qdrant, PostgreSQL, Redis Streams, and Node chat adapters.

Research confirmed the general architecture but found two implementation risks:

- TurboVec is promising as a local compressed read-path accelerator, but it should not replace the durable vector store in v1.
- One Qdrant collection per tenant can become operationally expensive at scale.

## Decision

Use this baseline:

| Layer | Baseline |
| --- | --- |
| Chat adapters | Node.js, grammY, discord.js |
| Control plane | Python, FastAPI |
| Persistence | PostgreSQL, SQLAlchemy 2.x, Alembic, RLS |
| Bus and jobs | Redis Streams, ARQ where Python-native |
| Agent workflow | LangGraph |
| Tool boundary | MCP |
| Durable RAG read path | LlamaIndex + Qdrant |
| Optional RAG accelerator | TurboVec candidate behind feature flag |
| RAG write path | CocoIndex adapter or equivalent indexing worker |
| Vector storage | Qdrant shared collection with tenant payload filters by default |
| Observability | OpenTelemetry-compatible traces, Langfuse-compatible LLM traces |

## Consequences

- ElizaOS and AgentScope remain design references, not runtime dependencies.
- TurboVec is a candidate accelerator with a formal adoption flow in ADR 0002.
- Tenant isolation must be validated in both PostgreSQL and Qdrant.
- Dedicated Qdrant collections are allowed only for enterprise isolation, high volume, or different embedding models.
- Pydantic schemas and SQLAlchemy ORM models remain separate. SQLModel is not part of the baseline unless a later ADR accepts it.

## Alternatives Considered

### ElizaOS as Core Runtime

Rejected for v1. Useful plugin ideas, but the platform needs direct control over tenancy, API contracts, audit logs, and storage isolation.

### AgentScope as Core Runtime

Rejected for v1. Useful permission/workspace concepts, but not required for the first production architecture.

### One Qdrant Collection Per Tenant

Rejected as the default. It can be used for specific tenants but should not be the baseline.

### TurboVec as Required Read Path

Rejected as required baseline. Keep it behind a feature flag until ADR 0002 gates pass.
