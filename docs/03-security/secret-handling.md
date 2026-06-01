# Secret Handling

Handle model + secret manager contract. KMS envelope encryption + Postgres credential table (ADR-006), GCP Cloud KMS (ADR-008).

## What Counts As A Secret

- Provider API keys (OpenAI, Anthropic).
- Tenant adapter credentials (Telegram bot tokens).
- Tenant tool credentials (crypto.price API keys, MCP server credentials).
- DB passwords, JWT secret.

## Envelope Encryption Model

```text
KMS master key (GCP Cloud KMS)  encrypts  DEK (Data Encryption Key)
DEK                             encrypts  secret material
DB stores: { ciphertext, dek_handle }     -- never raw secret
```

Resolve flow (just-in-time):
```text
read tenant_credential_handles {ciphertext, dek_handle}
-> KMSProvider.decrypt(dek_handle) -> DEK (in-memory)
-> decrypt(ciphertext, DEK) -> raw secret (in-memory, short-lived)
-> use in tool/adapter call
-> discard (no long cache, no log, no trace)
```

App never persists raw secret. App never logs DEK or secret.

## KMSProvider Interface

```python
class KMSProvider(Protocol):
    async def encrypt(self, plaintext: bytes) -> str: ...   # returns dek_handle/ciphertext ref
    async def decrypt(self, handle: str) -> bytes: ...
```

Implementations:
- `LocalKMSProvider` — file-based, **dev only**. Pre-flight reject trong production.
- `CloudKMSProvider` — GCP Cloud KMS (ADR-008, free tier 20K ops/month đủ MVP). Service account JSON mount ngoài git.

Provider behind interface → swap sang HashiCorp Vault Transit hoặc cloud KMS khác mà không sửa app.

## Credential Table

```sql
tenant_credential_handles (
    id, tenant_id, capability_id, secret_kind,
    ciphertext BYTEA,        -- secret encrypted by DEK
    dek_handle TEXT,         -- DEK encrypted by KMS master
    status, created_at, last_rotated_at
)
```

- `tenant_id` → RLS policy (ADR-002).
- Operator role BYPASSRLS cho emergency rotate, audited.
- Scope theo tenant + capability.

## Allowed vs Forbidden

| Allowed | Forbidden |
| --- | --- |
| `credential_handle` reference | Raw bot token trong tenant config |
| KMS envelope record | Provider API key trong plugin config |
| Redacted summary / hash | Secret trong prompt context |
| | Secret trong logs/traces/metrics labels |
| | Secret trong queue/outbox payloads |
| | Secret trong eval reports |
| | Broad platform token tới MCP servers |

## Production Pre-Flight (PRD-013)

On startup:
- Production env phải có `CloudKMSProvider` (hoặc Vault). Detect `LocalKMSProvider` → **fail closed** (refuse start).
- Reject dev/demo secrets + demo auth shortcuts.
- Verify KMS reachability (decrypt test với canary handle).

## Rotation

- Adapter/bot token rotate: new ciphertext + dek_handle, `last_rotated_at`, old status=revoked, audit.
- KMS DEK rotate: re-encrypt secrets dưới new DEK.
- Tenant deletion: DEK rotate/revoke → ciphertext không decrypt được (GDPR, xem persistence).

## Cost Note (ADR-008)

100 tenants × ~5 secrets × ~200 ops/month = ~100K ops < GCP free tier (20K/month... — nếu vượt, GCP KMS ~$0.03/10K ops ≈ vài USD/tháng). Cache DEK in-memory short-lived (per-worker) để giảm KMS API calls, không cache raw secret lâu.

## Validation

- Secret scan clean (detect-secrets baseline).
- No secret trong logs/traces (redaction test).
- Production rejects LocalKMSProvider.
- Credential handle scope enforcement (tenant + capability).
- Rotation produces audit + invalidates old.

## References

- [Security And Auditability](security-and-auditability.md)
- [Threat Model](threat-model.md)
- [ADR-006 Secret Manager](../06-decisions/adr-006-secret-manager.md)
- [ADR-008 Deployment Target](../06-decisions/adr-008-deployment-target.md)
