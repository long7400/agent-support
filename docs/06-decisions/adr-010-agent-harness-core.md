# ADR-010: Agent Harness Core

- **Status:** accepted
- **Date:** 2026-06-06
- **Deciders:** eng-lead, backend-eng, AI-engineer, product-owner
- **Related:** [core-agent-design.md](../01-architecture/core-agent-design.md), [adapters-and-integrations.md](../01-architecture/adapters-and-integrations.md), ADR-002, ADR-003, ADR-006, ADR-009

## Context

The current Core Agent design is graph-centric: LangGraph owns most workflow decisions, state movement, tool routing, policy checks, and model/tool loop behavior. That shape preserved durability and replay, but it risks turning graph nodes into a business-logic dumping ground and makes tenant policy, model policy, memory, tool permission, risk checks, human approval, and observability harder to compose and test independently.

LangChain now frames an agent as `Model + Harness`. The `create_agent` primitive provides the model/tool loop plus middleware, state/context schema, checkpointer support, streaming, and invocation by `thread_id`. LangChain middleware runs inside the compiled LangGraph returned by `create_agent`, which means the project can keep LangGraph as the durable runtime while moving lifecycle controls into explicit middleware.

Deep Agents is useful for delegated long-running or context-heavy work, but it is too broad and too expensive to become the default path for every support turn.

## Decision

Adopt a harness-first Core Agent architecture:

- **LangGraph remains the durable runtime** for worker orchestration, checkpoint/resume, interrupts, streaming, subgraphs, and deterministic non-agent steps.
- **LangChain `create_agent` becomes the default model/tool loop harness** for normal agent turns.
- **Product middleware is the control plane** for tenant context, platform constraints, prompt/context assembly, memory, model policy, capability exposure, tool guardrails, risk policy, human approval, audit, and observability.
- **Capability Runtime mediates every tool and delegated agent** through manifest validation, tenant enablement, risk/budget/rate checks, approval, timeout, output bounding, redaction, and audit.
- **Deep Agents is delegated only** for complex multi-step investigations, specialist reports, long-running workflows, approval pauses, or context-quarantined work. It is not the default FAQ, onboarding, moderation-screening, or single-step RAG path.

## Consequences

### Positive

- Cross-cutting controls become explicit middleware instead of prompt text or hidden graph-node logic.
- LangGraph durability and ADR-003 worker/outbox behavior remain intact.
- Tenant isolation and tool filtering can be tested at the capability runtime boundary.
- `LangGraphAgent` public methods can be preserved during migration while internals change behind a compatibility wrapper.
- Deep Agents can be approved, deferred, or disabled without blocking the base harness migration.

### Negative / Costs

- The codebase must introduce new contracts for harness state, invocation context, tenant harness profile, middleware ordering, and capability manifests.
- Existing `app/services/llm/service.py` retry/fallback behavior must be reconciled with `wrap_model_call` model policy to avoid duplicate fallback logic.
- Memory behavior must be designed carefully so existing long-term memory, LangGraph checkpoints, and any future Deep Agents memory do not duplicate or leak data.
- Middleware API details must be verified in a code spike before a full migration.

### Migration Constraints

- Preserve `LangGraphAgent.get_response`, `get_stream_response`, `get_chat_history`, and `clear_chat_history` until callers are migrated.
- Preserve Postgres checkpointing, Langfuse callbacks, memory search/add behavior, and outbox compatibility.
- Unit tests must use fake model/tool implementations and must not call real LLMs or external tools.
- Do not add `deepagents` to dependencies until package/API compatibility is verified and explicitly approved.
- Do not weaken fail-closed semantics for inactive tenants, denied tools, policy failures, or outbound delivery.

## Alternatives Considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| Keep graph-centric custom loop | Minimal short-term change, current docs already fit | Cross-cutting policy stays scattered, global tool binding risk remains, harder middleware testing | rejected |
| Use Deep Agents for all turns | Rich prebuilt harness, subagents, filesystem, summarization | Too much overhead and tool surface for FAQ/onboarding/moderation; dependency and latency creep | rejected |
| Build a custom loop without LangChain middleware | Maximum control | Recreates model/tool loop, checkpointer, streaming, middleware, and callback concerns manually | rejected |
| Harness-first with LangGraph + `create_agent` + middleware | Durable runtime stays, controls become modular, migration can be staged | Requires new contracts and API spike | chosen |

## Follow-up Actions

- Update `core-agent-design.md` with harness runtime, middleware stack, state/context contracts, capability runtime, Deep Agents boundaries, and migration/test plan.
- Align `adapters-and-integrations.md` so only trusted runtime events enter the harness and adapters remain thin translators.
- Run a code spike that verifies `create_agent` with current model/tool/checkpointer constraints before changing runtime code.
