# Phase 3: Agent Runtime Skeleton

**Goal:** replace generic chat loop với replayable domain graph (chạy trong worker, ADR-003).

## Scope

- `AgentState` (tenant-aware).
- Graph nodes: hydrate, classify, risk, route, policy, response, emit, record.
- `agent_runs`, `agent_run_steps`, `model_calls`, `graph_checkpoint_metadata`.
- Mock model/tool interfaces.
- Safe fallback + shadow behavior.
- Replay tests.

## Deliverables

### Graph (xem [core-agent-design.md](../01-architecture/core-agent-design.md))
```text
hydrate_context -> classify_intent -> risk_screen -> route
  -> support_rag_flow (stub rag.search)
  -> moderation_shadow_flow
  -> onboarding_flow
  -> safe_fallback
-> policy_check -> response_builder -> emit_outbound -> record_run
```
- Worker pulls from `processing_outbox` → runs graph (AsyncPostgresSaver checkpoint).
- `hydrate_context`: SET LOCAL tenant; reload status/policy/budget/capabilities.
- `tenant_id` immutable after hydration.

### Run Records
- `agent_runs` (trace, event, graph_version, config/policy version, status, latency).
- `agent_run_steps` (node, status, latency, redacted summary).
- `model_calls` (provider/model/prompt version/cost/tokens) — mocked in Phase 3.
- `graph_checkpoint_metadata` (thread_id → tenant_id, RLS-aware, ADR-002).
- Runtime guardrail settings: max graph wall time, max node retries, max prompt-visible state size, max tool/model calls per run, and worker concurrency. These must be env-configurable before enabling non-mocked model calls.

### Mock Interfaces
- `rag.search` stub (real Qdrant Phase 4) — graph depends on capability contract already.
- Fake model responses for unit tests (no real LLM).

### Safety
- Disabled tenant → stop before graph/outbound, record denied run.
- Empty/low-confidence → refuse/escalate.
- Outbound only after policy_check.

## Exit Criteria

- [ ] Saved trusted event replays with mocked outputs (deterministic).
- [ ] Tenant id immutable.
- [ ] No real LLM in unit tests.
- [ ] Outbound only after policy check.
- [ ] Run/step records created.
- [ ] Checkpoint resume works (worker crash → resume from checkpoint).
- [ ] Disabled tenant fails before graph execution.

## Validation

```bash
pytest tests/graph          # routing, tenant immutable, replay determinism
pytest tests/graph/replay   # mocked model/tool fixtures
```

Replay test: same trusted event + fixtures → same node sequence + same output.

## Risks

| Risk | Mitigation |
| --- | --- |
| Checkpointer bypasses RLS | tenant_id in checkpoint metadata + app-side filter (ADR-002). |
| Graph state leaks raw private data to trace | Bounded + redacted state; redaction tests. |
| Generic loop ships accidentally | Domain graph replaces template loop; routing tests. |
| Runtime overload from long graph runs | Enforce per-run timeout/budget and keep worker concurrency below DB pool/Compose caps. |

## References

- [Core Agent Design](../01-architecture/core-agent-design.md)
- [ADR-003 Graph Execution](../06-decisions/adr-003-graph-execution-mode.md)
- [Eval Datasets (Phase 3 focus)](../04-observability/eval-datasets.md)
