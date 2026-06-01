# ADR-006: Secret Manager Strategy

- **Status:** accepted
- **Date:** 2026-06-01
- **Deciders:** eng-lead, security-reviewer, devops
- **Related:** PRD-008, PRD-013, ADR-008, [secret-handling.md](../03-security/secret-handling.md)

## Context

Cần lưu: provider API keys (OpenAI/Anthropic), tenant adapter credentials (Telegram bot tokens), tenant tool credentials, DB passwords, JWT secret. Security docs cấm raw secrets trong config/prompt/log/trace; chỉ cho credential_handle references. 10-100 tenants × ~5 secrets.

## Decision

**KMS envelope encryption + Postgres credential table, sau `KMSProvider` interface.** KMS provider cụ thể quyết ở ADR-008 (GCP Cloud KMS).

## Consequences

### Positive
- Master key (KMS) encrypt DEK, DEK encrypt secret, store ciphertext + dek_handle trong DB.
- Resolve just-in-time: KMS decrypt DEK → decrypt secret → use → discard. Không log raw, không cache lâu.
- `tenant_credential_handles` có tenant_id → RLS (ADR-002).
- Tránh lock-in: KMSProvider interface, swap Vault Transit sau.

### Negative / Costs
- Setup phức tạp hơn raw config.
- Master key management vẫn cần KMS service.

### Follow-up actions
- `KMSProvider` interface: `LocalKMSProvider` (dev, reject prod), `CloudKMSProvider` (GCP).
- `tenant_credential_handles` table (Phase 1 skeleton, dùng Phase 2 cho bot token, Phase 5 cho tools).
- Pre-flight: production phải có CloudKMSProvider, fail closed nếu detect local (PRD-013).
- Cache DEK in-memory short-lived per-worker (giảm KMS calls).

## Alternatives Considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| HashiCorp Vault | Industry standard, dynamic secrets | Self-host ops, overkill MVP | rejected (defer) |
| AWS/GCP/Azure Secrets Manager | Managed, rotation | Cost ~$0.40/secret/month, API latency | rejected |
| Doppler/Infisical | Dev-friendly, free tier | Vendor lock, less control | rejected |
| Postgres + pgcrypto only | Same DB, no extra infra | Master key mgmt yếu nếu KMS-less | rejected |
| **KMS envelope + Postgres table** | App never sees cached raw, RLS, no lock-in | Setup phức tạp | **chosen** |

## Notes

Counter-argument: <10 tenants + team không quen KMS → pgcrypto với master key trong Docker secret. Nhưng compliance audit flag → SaaS enterprise cần KMS thật từ đầu. Cost: GCP KMS free tier 20K ops/month đủ MVP (ADR-008).
