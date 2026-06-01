# Phase 6: Moderation Enforcement And Review

**Goal:** move từ risk detection sang controlled action. Review UI = **Telegram bot review + minimal API** (Decision 12); web UI defer Phase 7+.

## Scope (outline)

- Policy matrix by category/action (`policy_versions`).
- Review queue (`review_queue_items`).
- Shadow/propose/enforce modes (`moderation_decisions`, `moderation_actions`).
- Platform moderation action tools (delete/ban/mute/warn) — idempotent.
- Telegram bot review channel (inline keyboard).
- False positive/negative regression set.

## Telegram Bot Review Flow (Decision 12)

```text
graph (mode=propose) -> moderation_decisions(pending)
-> worker post to tenant.review_chat_id (inline keyboard [Approve][Reject][Escalate])
-> admin tap -> callback_data {decision_id, action, hmac}
-> /v1/internal/moderation/callback
-> verify hmac + role (tenant_memberships) + decision pending
-> execute: approve -> moderation_actions + platform API; reject -> dismissed; escalate -> needs_review
-> audit (who, when, before/after) -> edit message with outcome
```

Minimal API: `GET /v1/admin/moderation/queue`, `POST /v1/admin/moderation/{id}/decision`. Web UI Phase 7 = presentation layer trên same API.

## Exit Criteria

- [ ] Shadow/propose/enforce modes behave as configured.
- [ ] Destructive actions audited + idempotent.
- [ ] Review override works (Telegram bot).
- [ ] No model text executes destructive action directly.

## Validation

```bash
pytest tests/moderation     # policy matrix, idempotency, callback verify, injection
```

## Risks

| Risk | Mitigation |
| --- | --- |
| Admin Telegram account compromise → fake approve | HMAC signature + 2FA admin login + role verify + rate limit. |
| Destructive action double-execute | idempotency_key UNIQUE. |

## References

- [Security And Auditability (moderation safety)](../03-security/security-and-auditability.md)
- [Core Agent Design (moderation flow)](../01-architecture/core-agent-design.md)
- [Eval Datasets (Phase 6 focus)](../04-observability/eval-datasets.md)
