# Agent Harness Boundary

`app.agent_harness` is the product core for agent execution. It owns the contracts and runtime path that turn trusted inbound events into policy-aware agent responses.

## Owns

- Runtime contracts for trusted events, tenant profiles, and execution results
- Middleware stack composition for validation, policy, budgets, and safety checks
- Capability registry integration and model-facing execution flow
- Replay support for deterministic inspection of prior runs
- Outbound policy checks before responses leave the harness

## Does Not Own

- Global app configuration, database setup, logging, or metrics plumbing
- HTTP route definitions, worker process bootstrapping, or platform ingest adapters
- Legacy LangGraph compatibility surfaces; callers should use the harness runtime directly

Keep dependencies pointed outward only when needed: the harness may use shared infrastructure, but infrastructure should not import the harness.
