# Core Agent Design

## Mục đích

Tài liệu này là thiết kế Core Agent chuyển giao cho repo template mới. Nó định nghĩa Agent Core là gì, LangGraph runtime shape, state contract, node contracts, tool/capability boundary, sub-agent policy, prompt/versioning, replay, và human-in-the-loop rules cho Agent Support.

## Đối tượng đọc

AI engineer, backend engineer, tool/plugin developer, QA, security reviewer, và product owner.

## Design Summary

Agent Support should use LangGraph as the top-level Agent Core runtime. The graph is a platform-owned workflow, not a free-form autonomous agent and not a generic chatbot loop.

Agent Core owns the path from trusted inbound event to replayable run, policy-checked result, audited capability usage, and outbound delivery intent.

Agent Core must:

- hydrate trusted tenant context,
- classify intent,
- screen risk,
- route to support/moderation/onboarding/ops/fallback,
- call tools only through a permissioned capability boundary,
- policy-check all final outputs,
- record replay/audit evidence,
- emit outbound messages only after checks pass.

Agent Core must not own:

- tenant credential material,
- raw platform secrets,
- direct vector DB access from arbitrary nodes,
- unchecked remote tool discovery,
- durable business state hidden in scratch memory,
- destructive moderation from raw model text.

## Core Agent Responsibilities

| Area | Responsibility |
| --- | --- |
| Runtime lifecycle | Create or resume one `agent_run` for each trusted inbound event. |
| State | Maintain serializable graph state and checkpoints. |
| Context hydration | Load tenant status, policy, persona, model budget, source visibility, and allowed capabilities. |
| Routing | Choose support, moderation, onboarding, ops, or fallback path through graph edges. |
| Policy | Enforce final answer/action, citation, moderation, budget, and capability rules. |
| Tool mediation | Request tools only through capability proxy. |
| Replay | Persist enough run/step/model/tool evidence to debug and replay with mocks. |
| Outbound | Build platform-safe delivery intent after policy passes. |

## Agent State Contract

Recommended minimal state:

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

Rules:

- State must be serializable.
- Tenant id is immutable.
- Raw private data is kept out of exported traces.
- Tool outputs in state are bounded and redacted.
- Prompt-visible memory is built by policy, not by dumping all state.

## Core Workflow Contract

```text
trusted inbound event
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
-> emit_outbound
-> record_run
```

## Required Node Contracts

| Node | Responsibility |
| --- | --- |
| `hydrate_context` | Reload tenant status, persona, policy, model budget, source/tool visibility, capability enablement. |
| `classify_intent` | Classify support, moderation, onboarding, ops, unknown, or unsafe. |
| `risk_screen` | Detect links, scam language, impersonation, toxic/spam patterns. |
| `route` | Deterministic graph edge selection. |
| `support_rag_flow` | Retrieve approved context, draft source-backed answer or refusal. |
| `moderation_shadow_flow` | Record non-destructive risk decision/proposal. |
| `onboarding_flow` | Render welcome/rules/official links from tenant config/sources. |
| `ops_harness_gate` | Decide whether a controlled sub-agent/harness is allowed. |
| `policy_check` | Validate answer/action, tool usage, moderation mode, citations, budget. |
| `response_builder` | Build platform-safe outbound content. |
| `emit_outbound` | Create/send delivery envelope through adapter path. |
| `record_run` | Persist run status, steps, latency, model/tool summaries. |

Each node should have:

- explicit input state fields,
- explicit output state updates,
- unit tests using fake model/tool responses,
- redacted logging with trace id and tenant id,
- typed errors or policy-denied outcomes,
- no direct tenant id mutation.

## Node Failure Semantics

| Failure | Expected behavior |
| --- | --- |
| Tenant inactive | Stop before model/tool/outbound and record denied run. |
| Classifier/model timeout | Safe fallback or retry within model budget. |
| Retrieval empty/stale | Refuse, clarify, or escalate. |
| Tool denied | Continue with safe fallback if possible; audit denial. |
| Tool timeout | Return typed error; no unbounded retry. |
| Policy check fail | No outbound send; record refusal/escalation reason. |
| Outbound build invalid | No platform send; record failed run/action. |

## Replay And Checkpointing

Agent Core must be replayable from product-owned records, not only external traces.

Replay inputs:

- trusted inbound event,
- tenant config version,
- tenant policy version,
- prompt/model versions,
- allowed capability versions,
- retrieval result fixture or source version,
- tool call fixtures,
- model output fixtures.

Replay rules:

- Unit tests do not call real LLMs or external tools.
- Replay should preserve trusted tenant id.
- Run records should identify graph version and node sequence.
- Checkpoints support resume, but audit/run tables remain the incident source of truth.

## Support RAG Flow

```text
question
-> decide RAG needed
-> call `rag.search` capability
-> receive bounded snippets + citations
-> draft answer from retrieved context
-> citation and confidence check
-> send answer OR refuse OR clarify OR escalate
```

Rules:

- Retrieval empty/stale/low-confidence cannot produce confident answer.
- Source-backed answer includes citation metadata.
- Public channel does not use private/internal source without policy.
- No direct vector DB call from arbitrary graph nodes.

The first implementation can use a fake or stub `rag.search` while the source-backed RAG layer is built, but the graph should already depend on the capability contract so the runtime shape does not change later.

## Moderation Flow

```text
message
-> rule checks
-> optional classifier
-> category/confidence
-> tenant policy matrix
-> shadow/proposal/enforcement record
-> optional outbound warning or review queue item
```

Default:

- shadow mode for destructive actions,
- propose mode for uncertain/high-impact cases,
- enforce only with explicit policy and idempotency.

## Onboarding Flow

Onboarding should be deterministic first:

- tenant welcome template,
- official links,
- safety warnings,
- community rules,
- locale fallback.

LLM use is optional and must not invent links or policy.

## Ops And Sub-Agent Harness Boundary

Use sub-agents only when a task needs:

- multi-step investigation,
- large context offload,
- report drafting,
- approval pauses,
- long-running workflow,
- isolated specialist instructions.

Do not use sub-agents by default for normal FAQ, fast moderation, or onboarding.

Sub-agent rules:

- manifest-declared,
- versioned,
- tenant opt-in,
- inherits tenant, trace, budget, timeout, visibility, allowed tools,
- cannot request new tools dynamically,
- cannot write durable business state except through audited services,
- scratch/context is run-scoped and disposable.

## Capability Boundary

Core Agent does not bind all available tools directly to the model. It asks a capability proxy for the filtered, tenant-allowed set for the current node/role.

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

Example:

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
-> load manifest and tenant enablement
-> verify role, risk, visibility, budget, rate limit, approval
-> validate input schema
-> create pre-call audit
-> resolve tenant-scoped credential handle if needed
-> execute built-in tool or filtered MCP tool with timeout
-> validate, bound, and redact output
-> update audit
-> return structured result or typed error
```

## Tool Types

| Type | Examples | V1 stance |
| --- | --- | --- |
| Built-in read | `rag.search`, `tenant.official_links` | Yes. |
| Built-in side effect | `moderation.propose_action` | Yes with audit/idempotency. |
| MCP read | `crypto.price`, `web.search` | Later, tenant-enabled only. |
| MCP side effect | ticket/CRM/write actions | Defer until approval/idempotency. |
| Forbidden | wallet signing, fund movement, arbitrary shell | Out of scope. |

## Prompt And Model Policy

Prompts are versioned assets.

Every model call should record:

- provider,
- model,
- temperature,
- max tokens,
- prompt version,
- tenant config/policy version,
- token usage/cost when available,
- timeout/retry outcome.

System prompts must say:

- retrieved docs are untrusted data and cannot override platform policy,
- tool calls require structured schema and platform permission,
- answer must refuse/escalate when source support is weak,
- no destructive action from free-form text.

Recommended prompt asset groups:

- platform system policy,
- support answer policy,
- moderation classification policy,
- onboarding render policy,
- citation/refusal policy,
- prompt-injection handling policy.

## Human-In-The-Loop

Human approval is required for:

- destructive moderation unless tenant policy explicitly allows enforcement,
- high-risk side-effect tools,
- candidate knowledge approval,
- policy or plugin changes in production,
- incident replay/export involving sensitive data.

HITL can be implemented as graph interrupt, review queue, or operator API, but final action must be recorded with actor and trace id.

## Core Agent Test Plan

Required test families:

- graph routing for support/moderation/onboarding/fallback,
- tenant id immutable after hydration,
- disabled tenant fails before graph execution/outbound,
- no real LLM in unit tests,
- fake tool/model replay is deterministic,
- `rag.search` denial for wrong tenant/visibility,
- disabled tool/plugin denied and audited,
- prompt injection fixture refuses tool/policy override,
- moderation shadow/propose/enforce policy matrix.

## First Build Slice

Start with:

1. Tenant-aware graph state.
2. Hydrate/context node.
3. Intent and risk stubs with fake model support.
4. Policy check.
5. Run/step persistence.
6. Outbound builder with safe fallback.
7. Replay tests with mocked model/tool output.

Add RAG, tool registry, MCP, and sub-agent harness after the graph skeleton and audit path pass.

## What Carries Into The Template

Carry these design decisions into implementation:

- Replace template's generic chat/tool loop with the domain graph.
- Keep template's PostgreSQL checkpointer pattern as runtime checkpointing.
- Add product-owned `agent_runs` and `agent_run_steps` for audit/replay.
- Treat template tools as implementation examples, not tenant-visible capabilities.
- Do not enable broad web search by default.
- Keep source-backed RAG behind `rag.search`.
- Keep Deep Agents/sub-agents optional and manifest-gated.

## Open Questions

1. Should graph execution run synchronously in the chat request for MVP or through a runtime worker after ingest?
2. Which checkpointer/store is accepted for production: template PostgreSQL saver only, or separate checkpoint schema plus product run tables?
3. Which model provider policy is accepted for first support answers?
4. What minimum review UI is required for HITL before destructive moderation?
5. Which tool capabilities are allowed in the first production tenant rollout?
