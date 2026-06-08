# ADR-009: Telegram Bot Strategy

- **Status:** accepted
- **Date:** 2026-06-01
- **Deciders:** eng-lead, backend-eng, product-owner
- **Related:** PRD-001, PRD-012, ADR-006, [adapters-and-integrations.md](../01-architecture/adapters-and-integrations.md)

## Context

Mỗi tenant cần kết nối Telegram bot vào community. 1 bot dùng chung cho all tenants với mapping, hay mỗi tenant 1 bot riêng? Multi-tenant SaaS từ đầu.

## Decision

**Per-tenant bot** — tenant tạo bot qua BotFather, submit token qua admin API. **Webhook mode** cho production.

## Consequences

### Positive
- Brand isolation: @MyProjectSupportBot (tenant own identity) — feature, không nice-to-have.
- Telegram rate-limit per-bot → 1 tenant spam không ảnh hưởng tất cả.
- Bot ban blast radius = 1 tenant (không phải toàn platform).

### Negative / Costs
- Onboarding cost: tenant phải BotFather setup (~10 phút).
- Adapter scale theo số tenant (webhook giảm worker count).

### Follow-up actions
- Onboarding flow: BotFather token → validate getMe → KMS encrypt (ADR-006) → `tenant_platforms` + credential handle.
- `setWebhook(url=/v1/webhook/telegram/{tenant_id}, secret_token=<random>)`.
- Verify secret_token mọi inbound. `my_chat_member` discover → channel mapping confirm.
- Fail-closed: invalid token, secret mismatch, unknown chat, bot ban → disable + alert.

## Alternatives Considered

| Option | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| **Per-tenant bot** | Brand isolation, per-bot rate limit, blast radius=1 | Onboarding cost | **chosen** |
| Shared bot + route by chat | Setup 1 lần | Brand chung, bot ban → all down, rate limit chung | rejected |
| Hybrid (shared free, per-tenant paid) | Linh hoạt | 2 path setup + monitoring | rejected |
| Per-tenant bắt buộc via onboarding | Sạch nhất | Onboarding cost cao | = chosen variant |

## Notes

Long-poll mode chỉ cho dev/sandbox. Production = webhook. Token storage qua KMS envelope (ADR-006), adapter resolve at runtime via credential handle. 1 FastAPI service handle tất cả tenants qua `/v1/webhook/telegram/{tenant_id}`.
