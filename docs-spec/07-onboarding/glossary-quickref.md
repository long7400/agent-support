# Glossary Quickref

Cheat sheet. Full glossary: [../00-foundation/glossary.md](../00-foundation/glossary.md).

## Decisions At A Glance

| Topic | Choice |
| --- | --- |
| Vector | Qdrant (app-layer tenant filter) — ADR-001 |
| Isolation | PostgreSQL RLS + SET LOCAL — ADR-002 |
| Async | Postgres outbox + worker (SKIP LOCKED) — ADR-003 |
| ORM | SQLAlchemy 2.0 + Pydantic v2 — ADR-004 |
| Auth | JWT user + service principals + memberships — ADR-005 |
| Secrets | KMS envelope + Postgres table — ADR-006 |
| Traces | Langfuse self-host — ADR-007 |
| Deploy | Single VPS + Compose + GCP KMS — ADR-008 |
| Telegram | Per-tenant bot + webhook — ADR-009 |

## Key Invariants

- `tenant_id` từ trusted context only (never request body).
- `tenant_id` immutable sau hydration.
- `SET LOCAL app.current_tenant` trong `db.begin()` (else leak).
- Qdrant query luôn có tenant filter (else fail closed).
- Secret = handle, never raw.
- Outbound only after policy_check.
- No destructive moderation từ raw model text.
- audit_events = source of truth (not traces).

## Status Vocabulary

| Field | Values |
| --- | --- |
| Tenant | active / disabled / suspended / deleting |
| Moderation mode | shadow / propose / enforce |
| Source version | parsing / verifying / active / tombstoned |
| Outbox | pending / processing / done / dead_letter |
| Visibility | public / private / internal |
| Actor | user / tenant_admin / moderator / operator / adapter / worker / tool |

## Common Commands

```bash
make docker-compose-up ENV=development
make migrate / make migration MSG="..." / make migrate-downgrade
make check          # lint + typecheck
make eval-quick
pytest tests/isolation     # cross-tenant denial
detect-secrets scan --baseline .secrets.baseline
```

## Built-in Capabilities

`rag.search`, `tenant.official_links`, `moderation.propose_action`, `support.escalate`. (MCP: `crypto.price`, `web.search` — tenant-enabled later.)

## Tool Deny Codes

`TOOL_NOT_FOUND`, `PLUGIN_DISABLED`, `CAPABILITY_DISABLED`, `TOOL_INPUT_INVALID`, `TOOL_CREDENTIAL_UNAVAILABLE`, `TOOL_TIMEOUT`, `TOOL_POLICY_DENIED`, `TOOL_OUTPUT_INVALID`.

## References

- [Full Glossary](../00-foundation/glossary.md)
- [README index](../README.md)
