# Research Report: Crypto Agent Platform Stack

**Date:** 2026-05-28  
**Scope:** turn `spec.md` into a production baseline for a multi-tenant crypto community agent platform.

## Executive Summary

The original stack is directionally good: Node adapters for chat platforms, FastAPI for the control plane, LangGraph for agent orchestration, MCP for tool boundaries, Qdrant for vector storage, and a separate incremental indexing service for knowledge freshness.

Two assumptions need tightening before implementation:

- `TurboVecVectorStore` is not accepted as baseline. The production baseline is LlamaIndex with the official Qdrant integration. TurboVec stays experimental until a maintained integration and benchmark are proven.
- "One Qdrant collection per tenant" is not the default. Qdrant recommends partitioning by payload for many tenants; dedicated collections are reserved for enterprise or high-volume tenants.

## Sources Consulted

| Topic | Source |
| --- | --- |
| MCP tool boundary | https://modelcontextprotocol.io/docs/concepts/tools |
| LangGraph persistence | https://docs.langchain.com/oss/python/langgraph/persistence |
| FastAPI deployment | https://fastapi.tiangolo.com/deployment/concepts/ |
| Qdrant multi-tenancy | https://qdrant.tech/documentation/guides/multiple-partitions/ |
| LlamaIndex Qdrant | https://docs.llamaindex.ai/en/stable/examples/vector_stores/QdrantIndexDemo/ |
| CocoIndex docs entry | https://cocoindex.io/docs/ |
| ElizaOS docs index | https://docs.elizaos.ai/llms.txt |
| AgentScope v2 docs index | https://docs.agentscope.io/llms.txt |

## Key Findings

### 1. Control Plane

FastAPI is a strong fit for tenant configuration, admin APIs, sync orchestration, health checks, and internal service APIs. Production docs should explicitly include deployment concerns: process manager, proxy, TLS termination, worker count, health probes, and graceful shutdown.

Baseline:

- FastAPI app owns tenant config, plugin config, auth, billing-ready metadata, audit logs, and job APIs.
- PostgreSQL is the source of truth for configuration and transactional state.
- Redis Streams is used for chat ingress/egress and consumer groups.
- ARQ can be used for background jobs when jobs are Python-native and Redis-backed.

### 2. Agent Engine

LangGraph is suitable for deterministic agent workflows because it gives explicit state, graph nodes, persistence/checkpointing, and resumability. Production docs should avoid "agent magic" and name every graph node and state transition.

Baseline graph:

- `classify_intent`
- `moderation_guard`
- `route_plugin`
- `retrieve_knowledge`
- `draft_response`
- `policy_check`
- `emit_response`

### 3. MCP Boundary

MCP is a good tool boundary, but it should not replace internal service contracts. MCP tools should be treated as permissioned capabilities with typed input/output schemas, timeouts, audit logs, and tenant-scoped credentials.

Baseline MCP tool classes:

- `rag.search`
- `web.search`
- `crypto.price`
- `moderation.classify`
- `community.member_lookup`

### 4. RAG and Knowledge Indexing

LlamaIndex + Qdrant is the safer baseline. CocoIndex can own incremental crawling/indexing, but each connector must be proven with integration tests before it becomes production-critical.

Baseline read path:

- Query rewrite.
- Qdrant vector search filtered by `tenant_id`, `source_id`, and visibility metadata.
- Optional hybrid search/rerank.
- Prompt context builder with citation metadata.

Baseline write path:

- Source crawl.
- Normalize.
- Chunk.
- Embed.
- Upsert.
- Mark sync status and source version.

### 5. Multi-Tenancy

Database isolation must be enforced at several layers:

- API authorization.
- PostgreSQL RLS.
- Vector payload filters.
- Tenant-aware Redis stream names or message envelopes.
- Tenant-scoped tool credentials.

Default Qdrant layout:

- One collection per embedding model and domain version, for example `knowledge_chunks_v1`.
- Required payload indexes: `tenant_id`, `source_id`, `visibility`, `updated_at`.
- Dedicated tenant collection only for isolation tier or extreme volume.

### 6. ElizaOS and AgentScope

ElizaOS and AgentScope are useful design references, not the core runtime baseline. This platform should borrow:

- Plugin registry ideas from ElizaOS.
- Workspace/tool/permission concepts from AgentScope.

It should not couple the backend to either framework until there is a direct business reason.

## Production Recommendations

1. Build the core as a Python service boundary first: FastAPI, SQLModel or SQLAlchemy, Alembic, Redis, Qdrant, LangGraph.
2. Keep Node adapters thin. They should translate Telegram/Discord events into internal envelopes and emit responses.
3. Use MCP only at capability boundaries. Internal DB reads, tenant config, and moderation policy are not MCP tools by default.
4. Use Postgres RLS plus application-level tenant checks. RLS is a backstop, not the only guard.
5. Treat every LLM output as untrusted until policy-checked and bounded by tool permissions.
6. Build with tracing and replay from day one. Agent bugs are easiest to fix from durable event logs.

## Open Questions

- Which tenant auth model ships first: API key, OAuth, or admin-only local accounts?
- Which embedding model is accepted for v1: OpenAI, Cohere, BGE, or provider-configurable?
- Does the first release need paid billing, or only tenant quota tracking?
- Which chat platform is first: Telegram or Discord?
