# Phase 5: Capability Registry And Tools

**Goal:** make tools safe + tenant-configurable. Secret resolution via KMS (ADR-006).

## Scope (outline)

- Capability manifest schema + registry (`plugin_manifests`, `plugin_capabilities`).
- Tenant capability enablement (`tenant_capability_enablement`, `tenant_tool_policies`).
- Tool proxy (predicate-gated, xem [core-agent-design.md](../01-architecture/core-agent-design.md)).
- Tool audit records (`tool_calls`).
- Secret handle resolution (KMS envelope, `tenant_credential_handles`).
- Built-in `rag.search`; add `crypto.price` chỉ khi credentials/rate limits ready.
- URL allowlist knowledge source (Decision 10 — Phase 5).

## Tool Proxy Predicate

```text
tenant active AND capability enabled AND role allowed AND risk allowed
AND input schema valid AND budget/rate limit available AND timeout configured
AND credential handle available (if required) AND approval satisfied (if required)
```

Denied → typed error + audit, no underlying call. Output bound/redact before prompt.

## Exit Criteria

- [ ] Disabled tool cannot execute.
- [ ] Tool input/output schemas enforced.
- [ ] Tool denials audited.
- [ ] Secrets absent from logs/traces/config.
- [ ] Missing credential fails closed (TOOL_CREDENTIAL_UNAVAILABLE).

## Validation

```bash
pytest tests/tools          # disabled/missing/invalid/timeout/credential failure
```

## Notes

- MCP read tools (`crypto.price`, `web.search`) tenant-enabled only, no token passthrough.
- Side-effecting tools need idempotency + approval.

## References

- [ADR-006 Secret Manager](../06-decisions/adr-006-secret-manager.md)
- [Secret Handling](../03-security/secret-handling.md)
- [Core Agent Design](../01-architecture/core-agent-design.md)
