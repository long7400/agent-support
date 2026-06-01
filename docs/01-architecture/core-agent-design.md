# Core Agent Design

## Mục đích

Thiết kế Core Agent: LangGraph runtime shape, state contract, node contracts, tool/capability boundary, sub-agent policy, prompt/versioning, replay, human-in-the-loop.

## Đối tượng đọc

AI engineer, backend engineer, tool/plugin developer, QA, security reviewer, product owner.

## Design Summary

Agent Support dùng LangGraph làm top-level Agent Core runtime. Graph là **platform-owned workflow**, không phải free-form autonomous agent, không phải generic chatbot loop. Graph chạy trong **worker** (sau khi outbox claim event), không trong HTTP request path (ADR-003).

Agent Core own đường từ trusted inbound event → replayable run → policy-checked result → audited capability usage → outbound delivery intent.

Agent Core PHẢI: hydrate trusted tenant context, classify intent, screen risk, route, call tools chỉ qua permissioned capability boundary, policy-check mọi output, record replay/audit evidence, emit outbound chỉ sau khi checks pass.

Agent Core KHÔNG own: tenant credential material, raw platform secrets, direct vector DB access từ arbitrary nodes, unchecked remote tool discovery, durable business state ẩn trong scratch memory, destructive moderation từ raw model text.

## Core Agent Responsibilities

| Area | Responsibility |
| --- | --- |
| Runtime lifecycle | Create/resume một `agent_run` cho mỗi trusted inbound event. |
| State | Maintain serializable graph state + checkpoints (AsyncPostgresSaver). |
| Context hydration | Load tenant status, policy, persona, model budget, source visibility, allowed capabilities. |
| Routing | Choose support/moderation/onboarding/ops/fallback qua graph edges. |
| Policy | Enforce final answer/action, citation, moderation, budget, capability rules. |
| Tool mediation | Request tools chỉ qua capability proxy. |
| Replay | Persist đủ run/step/model/tool evidence để debug và replay với mocks. |
| Outbound | Build platform-safe delivery intent sau khi policy pass. |

## Agent State Contract

```python
class AgentState(TypedDict):
    trace_id: str
    tenant_id: str
    input_event_id: str
    platform: Literal["telegram", "discord"]
    channel_id: str
    thread_id: str | None
    user_id_hash: str
    message_id: str
    inbound_text_preview: str
    messages: list[dict[str, object]]
    tenant_config_version: int
    tenant_policy_version: int
    model_policy: dict[str, object]
    allowed_capabilities: list[str]
    intent: dict[str, object] | None
    risk: dict[str, object] | None
    retrieval_context: list[dict[str, object]]
    tool_results: list[dict[str, object]]
    moderation_decision: dict[str, object] | None
    final_response: dict[str, object] | None
    audit_refs: list[str]
```

Rules: state serializable; `tenant_id` immutable; raw private data ngoài exported traces; tool outputs trong state bounded + redacted; prompt-visible memory build bởi policy, không dump toàn state.

## Core Workflow Contract

```text
trusted inbound event (from processing_outbox)
-> hydrate_context
-> classify_intent
-> risk_screen
-> route
   -> support_rag_flow
   -> moderation_shadow_flow
   -> onboarding_flow
   -> ops_harness_gate
   -> safe_fallback
-> policy_check
-> response_builder
-> emit_outbound     # writes delivery_outbox
-> record_run
```

## Required Node Contracts

| Node | Responsibility |
| --- | --- |
| `hydrate_context` | Reload tenant status, persona, policy, model budget, source/tool visibility, capability enablement. Set tenant context (SET LOCAL). |
| `classify_intent` | Classify support/moderation/onboarding/ops/unknown/unsafe. |
| `risk_screen` | Detect links, scam language, impersonation, toxic/spam patterns. |
| `route` | Deterministic graph edge selection. |
| `support_rag_flow` | Retrieve approved context, draft source-backed answer hoặc refusal. |
| `moderation_shadow_flow` | Record non-destructive risk decision/proposal. |
| `onboarding_flow` | Render welcome/rules/official links từ tenant config/sources. |
| `ops_harness_gate` | Decide controlled sub-agent/harness có được phép không. |
| `policy_check` | Validate answer/action, tool usage, moderation mode, citations, budget. |
| `response_builder` | Build platform-safe outbound content. |
| `emit_outbound` | Create delivery envelope → delivery_outbox. |
| `record_run` | Persist run status, steps, latency, model/tool summaries. |

Mỗi node: explicit input/output state fields, unit tests với fake model/tool, redacted logging (trace id + tenant id), typed errors/policy-denied outcomes, no tenant id mutation.

## Node Failure Semantics

| Failure | Expected behavior |
| --- | --- |
| Tenant inactive | Stop trước model/tool/outbound, record denied run. |
| Classifier/model timeout | Safe fallback hoặc retry trong model budget. |
| Retrieval empty/stale | Refuse, clarify, hoặc escalate. |
| Tool denied | Continue safe fallback nếu được; audit denial. |
| Tool timeout | Typed error; no unbounded retry. |
| Policy check fail | No outbound send; record refusal/escalation reason. |
| Outbound build invalid | No platform send; record failed run/action. |

## Replay And Checkpointing

Replay từ product-owned records, không chỉ external traces.

Replay inputs: trusted inbound event, tenant config/policy version, prompt/model versions, allowed capability versions, retrieval fixture/source version, tool call fixtures, model output fixtures.

Replay rules:
- Unit tests không gọi real LLM/external tools.
- Replay preserve trusted tenant id.
- Run records identify graph version + node sequence.
- Checkpoints support resume; audit/run tables = incident source of truth.

> **Checkpointer + RLS (ADR-002):** AsyncPostgresSaver dùng cùng connection pool nhưng không tự set tenant context. Giải: include `tenant_id` trong checkpoint metadata + filter app-side. Worker crash giữa graph → checkpoint còn → restart pick up cùng event (status=processing + worker heartbeat) → resume từ checkpoint.

## Support RAG Flow

```text
question
-> decide RAG needed
-> call rag.search capability (qua proxy)
-> receive bounded snippets + citations (Qdrant, tenant-filtered)
-> draft answer từ retrieved context
-> citation + confidence check
-> send answer OR refuse OR clarify OR escalate
```

Rules: empty/stale/low-confidence không sinh confident answer; source-backed answer có citation metadata; public channel không dùng private/internal source without policy; no direct vector DB call từ arbitrary nodes. Phase 3 có thể dùng stub `rag.search`, nhưng graph đã depend vào capability contract.

## Moderation Flow

```text
message -> rule checks -> optional classifier -> category/confidence
-> tenant policy matrix -> shadow/proposal/enforcement record
-> optional outbound warning hoặc review queue item
```

Default: shadow cho destructive actions; propose cho uncertain/high-impact; enforce chỉ với explicit policy + idempotency. Review UI Phase 6 = Telegram bot inline keyboard (xem roadmap Phase 6).

## Onboarding Flow

Deterministic-first: tenant welcome template, official links, safety warnings, community rules, locale fallback. LLM optional, không invent links/policy.

## Ops And Sub-Agent Harness Boundary

Sub-agents chỉ khi task cần: multi-step investigation, large context offload, report drafting, approval pauses, long-running workflow, isolated specialist instructions. KHÔNG dùng mặc định cho normal FAQ, fast moderation, onboarding.

Sub-agent rules: manifest-declared, versioned, tenant opt-in, inherit tenant/trace/budget/timeout/visibility/allowed tools, không request tool động, không write durable business state trừ qua audited services, scratch run-scoped disposable.

## Capability Boundary

Core Agent không bind all tools trực tiếp. Hỏi capability proxy filtered set theo node/role.

Runtime predicate:
```text
tenant active
and plugin/capability enabled
and agent role allowed
and risk level allowed
and input schema valid
and budget/rate limit available
and timeout configured
and credential handle available when required
and approval gate satisfied when required
```

## Capability Manifest Example

```yaml
schema_version: "1"
plugin_name: "support_core"
version: "0.1.0"
owner: "platform"
capabilities:
  - name: "rag.search"
    type: "tool"
    risk_level: "read_sensitive"
    input_schema_ref: "schemas/rag.search.input.json"
    output_schema_ref: "schemas/rag.search.output.json"
    allowed_agent_roles: ["support"]
    default_timeout_ms: 3000
    max_timeout_ms: 8000
    retry_policy: "read_idempotent"
    audit_event: "tool.rag.search"
    implementation:
      kind: "built_in"
      ref: "rag_search"
  - name: "support-investigator"
    type: "sub_agent"
    risk_level: "read_sensitive"
    allowed_tools: ["rag.search"]
    max_steps: 6
    timeout_ms: 15000
    prompt_version: "support-investigator@0.1.0"
config_schema_ref: "schemas/config.json"
secret_refs: []
tests:
  contract_fixtures:
    - "tests/contracts/rag.search.json"
```

## Tool Execution Contract

```text
graph requests capability
-> normalize name
-> load manifest + tenant enablement
-> verify role, risk, visibility, budget, rate limit, approval
-> validate input schema
-> create pre-call audit
-> resolve tenant-scoped credential handle nếu cần (KMS decrypt, ADR-006)
-> execute built-in tool hoặc filtered MCP tool với timeout
-> validate, bound, redact output
-> update audit
-> return structured result hoặc typed error
```

## Tool Types

| Type | Examples | V1 stance |
| --- | --- | --- |
| Built-in read | `rag.search`, `tenant.official_links` | Yes. |
| Built-in side effect | `moderation.propose_action` | Yes với audit/idempotency. |
| MCP read | `crypto.price`, `web.search` | Later, tenant-enabled only. |
| MCP side effect | ticket/CRM/write actions | Defer until approval/idempotency. |
| Forbidden | wallet signing, fund movement, arbitrary shell | Out of scope. |

## Prompt And Model Policy

Prompts là versioned assets. Mỗi model call record: provider, model, temperature, max tokens, prompt version, tenant config/policy version, token usage/cost, timeout/retry outcome.

System prompts phải nói: retrieved docs là untrusted data không override platform policy; tool calls cần structured schema + platform permission; answer phải refuse/escalate khi source support yếu; no destructive action từ free-form text.

Prompt asset groups: platform system policy, support answer policy, moderation classification policy, onboarding render policy, citation/refusal policy, prompt-injection handling policy.

## Human-In-The-Loop

Human approval bắt buộc cho: destructive moderation (trừ policy explicit cho enforce), high-risk side-effect tools, candidate knowledge approval, policy/plugin changes in production, incident replay/export với sensitive data.

HITL impl = graph interrupt, review queue, hoặc operator API. Phase 6 = Telegram bot review (inline keyboard). Final action record với actor + trace id.

## Core Agent Test Plan

- Graph routing support/moderation/onboarding/fallback.
- Tenant id immutable sau hydration.
- Disabled tenant fail trước graph execution/outbound.
- No real LLM trong unit tests.
- Fake tool/model replay deterministic.
- `rag.search` denial cho wrong tenant/visibility.
- Disabled tool/plugin denied + audited.
- Prompt injection fixture refuse tool/policy override.
- Moderation shadow/propose/enforce policy matrix.

## First Build Slice (Phase 3)

1. Tenant-aware graph state.
2. hydrate_context node.
3. Intent + risk stubs với fake model.
4. policy_check.
5. Run/step persistence.
6. Outbound builder với safe fallback.
7. Replay tests với mocked model/tool.

RAG, tool registry, MCP, sub-agent harness sau khi graph skeleton + audit path pass.

## Resolved Open Questions

- Graph execution → worker sau ingest (ADR-003), không sync request.
- Checkpointer → template AsyncPostgresSaver + tenant_id trong metadata + product run tables.
- Review UI cho HITL → Telegram bot review Phase 6.

## References

- [System Architecture](system-architecture.md)
- [Adapters And Integrations](adapters-and-integrations.md)
- [ADR-003 Graph Execution](../06-decisions/adr-003-graph-execution-mode.md)
- [Eval Datasets](../04-observability/eval-datasets.md)
