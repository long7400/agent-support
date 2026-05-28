# Agent Support Documentation

This directory is the source of truth for the Crypto Agent Platform design.
`spec.md` remains the original input brief; the files here are the production-ready working docs.

## Reading Order

1. [Research Report](research/260528-platform-stack-research.md) - what changed after checking current docs.
2. [Production Spec](production-spec.md) - product scope, requirements, system boundaries.
3. [System Architecture](system-architecture.md) - runtime components, data flows, tenancy, security.
4. [Technical Plan](technical-plan.md) - implementation phases and engineering sequence.
5. [Task Breakdown](task-breakdown.md) - actionable backlog with acceptance criteria.
6. [Implementation Flow](implementation-flow.md) - day-to-day build and delivery loop.
7. [Validation Checklist](validation-checklist.md) - gates before merge, release, and production.
8. [Coding Rules](coding-rules.md) - code standards for this repo.
9. [Agent Instructions](../AGENTS.md) - operating rules for coding agents.
10. [ADR 0001](decisions/0001-production-stack-baseline.md) - accepted stack baseline and rejected assumptions.
11. [ADR 0002](decisions/0002-turbovec-read-path-accelerator.md) - TurboVec evaluation and adoption gates.

## Documentation Rules

- Keep durable project docs in `docs/`.
- Keep local scratch plans out of git under `plans/` or `plan/`.
- Update `docs/decisions/` when a production decision changes.
- Update the validation checklist before adding new runtime surfaces.
- Keep `AGENTS.md` aligned with `docs/coding-rules.md` when agent workflow or code standards change.
