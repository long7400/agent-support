# Infra Boundary

`app.infra` contains shared application infrastructure. It is the place for cross-cutting runtime services that product code depends on but does not own.

## Owns

- Configuration and environment-backed settings
- Database sessions, tenant context, and persistence wiring
- Logging, metrics, observability, and runtime guardrails
- Cache, KMS, rate limiting, and middleware primitives
- Process-level helpers used by API, workers, services, and tests

## Does Not Own

- Agent runtime behavior or product orchestration
- Capability definitions, replay semantics, or outbound policy decisions
- API route business logic or tenant control-plane workflows

Keep this package stable and boring. Modules here should expose small, reusable contracts and avoid depending on product-specific agent code.
