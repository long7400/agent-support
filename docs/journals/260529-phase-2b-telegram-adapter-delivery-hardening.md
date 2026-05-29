# Phase 2B Telegram Adapter And Delivery Hardening

## Scope

Phase 2B connects the first real sandbox platform edge and hardens Redis
delivery behavior without starting Discord runtime, LangGraph, RAG, MCP,
Celery, dashboard UI, production webhook deployment, or production secret
manager integration.

## Delivered

- Added adapter-specific auth for `/internal/messages/ingest` through
  `X-Adapter-Token`, separate from admin and internal tokens.
- Kept tenant identity trusted by resolving platform workspace/channel mapping in
  the control plane; adapter request bodies still cannot supply `tenant_id`.
- Added an explicit outbound delivery envelope with sendable text, reply target,
  tenant id, trace id, platform, and source chat event id.
- Added a local TypeScript Telegram adapter using grammY long polling for text
  message normalization and a mocked-testable HTTP client.
- Added Telegram outbound stream delivery that creates its consumer group,
  calls `sendMessage`, and ACKs only after send success.
- Added Redis pending inspection, `XAUTOCLAIM` reclaim, retry-limit DLQ publish,
  and deterministic `agent-support-message-reclaim` CLI.
- Documented Phase 2B env vars, adapter package gates, Redis inspection, and
  deferred boundaries.

## Validation Focus

- Python unit and integration tests cover adapter auth, outbound contracts,
  Redis reclaim parsing, DLQ payload shape, and reclaim worker behavior.
- Adapter tests cover Telegram normalization, control-plane auth headers,
  outbound send/ACK order, and outbound consumer group creation.
- Full validation should include Python lint/type/unit gates, adapter lint/type
  and tests, Docker-backed Alembic upgrade, integration tests, and secret scan.

## Deferred

- Production adapter credential storage and secret rotation.
- Telegram webhook deployment and Telegram webhook secret validation.
- Discord runtime.
- LangGraph, RAG, Qdrant indexing, MCP tools, and Celery chat transport.
