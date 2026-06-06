"""Delivery sender guardrail tests (Task 8).

Source-based tests verifying the delivery sender implements
required patterns: SKIP LOCKED, receipts, rate limiting, sandbox sender.
"""

from pathlib import Path

DELIVERY_SENDER = Path("app/services/delivery_sender.py")
RATE_LIMITS = Path("app/services/rate_limits.py")
WORKER_PROCESS = Path("app/worker.py")


def test_delivery_sender_uses_skip_locked() -> None:
    """claim_delivery must use FOR UPDATE SKIP LOCKED for safe concurrent claiming."""
    source = DELIVERY_SENDER.read_text()
    assert "FOR UPDATE SKIP LOCKED" in source
    assert "claim_delivery" in source


def test_delivery_sender_claims_pending_only() -> None:
    """claim_delivery must filter for status='pending' and run_after_ts <= now."""
    source = DELIVERY_SENDER.read_text()
    assert "status = 'pending'" in source
    assert "run_after_ts <=" in source
    assert "dead_letter = false" in source


def test_delivery_sender_sets_processing_status() -> None:
    """claim_delivery must mark claimed rows as 'processing' with worker_id."""
    source = DELIVERY_SENDER.read_text()
    assert "status = 'processing'" in source
    assert "worker_id" in source
    assert "heartbeat_at" in source


def test_delivery_sender_orders_by_created_at() -> None:
    """claim_delivery must order by created_at ASC for FIFO delivery."""
    source = DELIVERY_SENDER.read_text()
    assert "ORDER BY created_at ASC" in source


def test_delivery_sender_reclaims_stale() -> None:
    """reclaim_stale_delivery must detect and reset stuck processing rows."""
    source = DELIVERY_SENDER.read_text()
    assert "reclaim_stale_delivery" in source
    assert "stale_cutoff" in source or "stale_after" in source
    assert 'status == "processing"' in source
    assert "heartbeat_at <" in source


def test_delivery_sender_creates_receipts() -> None:
    """send_delivery must create DeliveryReceipt on success."""
    source = DELIVERY_SENDER.read_text()
    assert "DeliveryReceipt" in source
    assert "send_delivery" in source
    assert "platform_message_id" in source


def test_delivery_sender_marks_delivered() -> None:
    """send_delivery must mark delivery as 'delivered' after success."""
    source = DELIVERY_SENDER.read_text()
    assert '"delivered"' in source
    assert "status" in source


def test_delivery_sender_checks_idempotency() -> None:
    """send_delivery must check for existing receipt before sending."""
    source = DELIVERY_SENDER.read_text()
    # Must check existing receipt by delivery_outbox_id
    assert "delivery_outbox_id" in source
    assert "existing_receipt" in source or "existing" in source


def test_delivery_sender_implements_telegram_sandbox() -> None:
    """_send_telegram must implement sandbox sender (no real API calls)."""
    source = DELIVERY_SENDER.read_text()
    assert "_send_telegram" in source
    assert "sandbox" in source.lower()
    assert "tg:sandbox:" in source


def test_delivery_sender_checks_rate_limits() -> None:
    """_send_telegram must check rate limits before sending."""
    source = DELIVERY_SENDER.read_text()
    assert "check_telegram_rate_limits" in source
    assert "rate_limited" in source


def test_delivery_sender_returns_typed_result() -> None:
    """_send_telegram and _send_discord must return typed platform send results."""
    source = DELIVERY_SENDER.read_text()
    assert "class PlatformSendResult" in source
    assert ") -> PlatformSendResult" in source
    assert 'PlatformSendResult("success"' in source
    assert 'PlatformSendResult("rate_limited"' in source


def test_delivery_sender_discord_not_implemented() -> None:
    """_send_discord must return rate_limited (Phase 7+ placeholder)."""
    source = DELIVERY_SENDER.read_text()
    assert "_send_discord" in source
    assert "discord_sender_not_implemented" in source
    assert "3600.0" in source  # 1 hour retry


def test_delivery_sender_schedules_retry() -> None:
    """_schedule_retry must implement exponential backoff with cap."""
    source = DELIVERY_SENDER.read_text()
    assert "_schedule_retry" in source
    assert "_compute_backoff" in source
    assert "2**" in source or "2 **" in source  # exponential
    assert "RETRY_BACKOFF_MAX_SECONDS" in source


def test_delivery_sender_moves_to_dlq() -> None:
    """_schedule_retry must move to dead_letter after max retries."""
    source = DELIVERY_SENDER.read_text()
    assert "_mark_dlq" in source
    assert "RETRY_MAX_ATTEMPTS" in source
    assert "dead_letter" in source


def test_delivery_sender_uses_tenant_context() -> None:
    """run_cycle must process deliveries within tenant context."""
    source = DELIVERY_SENDER.read_text()
    assert "with_tenant_context" in source


def test_delivery_sender_handles_errors() -> None:
    """send_delivery must catch exceptions and schedule retries."""
    source = DELIVERY_SENDER.read_text()
    assert "except Exception" in source
    assert "_schedule_retry" in source


def test_delivery_sender_bounds_error_messages() -> None:
    """Error messages stored in last_error must be bounded."""
    source = DELIVERY_SENDER.read_text()
    # Check that error strings are truncated
    assert "[:1000]" in source or "[:500]" in source


def test_delivery_sender_audits_retry_scheduled() -> None:
    """Delivery retries must be persisted as audit events, not only logged."""
    source = DELIVERY_SENDER.read_text()
    assert "delivery_retry_scheduled" in source
    assert "await emit_audit_event" in source
    assert 'action="delivery_retry_scheduled"' in source


def test_delivery_sender_audits_platform_auth_failure() -> None:
    """Invalid-token/403 responses must produce a terminal audit path."""
    source = DELIVERY_SENDER.read_text()
    assert "is_invalid_token" in source
    assert "http_status in (401, 403)" in source
    assert 'action="delivery_platform_auth_failed"' in source


def test_delivery_sender_discovers_tenants() -> None:
    """get_tenants_with_pending_delivery must scan for work across tenants."""
    source = DELIVERY_SENDER.read_text()
    assert "get_tenants_with_pending_delivery" in source
    assert "distinct" in source.lower() or ".distinct()" in source


def test_delivery_sender_logs_without_secrets() -> None:
    """Delivery sender logs must not include raw secrets or sensitive data."""
    source = DELIVERY_SENDER.read_text()
    # Should log structured events, not raw data
    assert "logger.info" in source
    assert "logger.warning" in source
    # Must not log bot tokens or raw payloads
    assert "bot_token" not in source
    assert "raw_payload" not in source


def test_rate_limiter_implements_token_bucket() -> None:
    """RateLimiter must implement token bucket algorithm."""
    source = RATE_LIMITS.read_text()
    assert "TokenBucket" in source
    assert "capacity" in source
    assert "refill_rate" in source
    assert "try_acquire" in source


def test_rate_limiter_checks_telegram_limits() -> None:
    """check_telegram_rate_limits must check chat, group, and global rates."""
    source = RATE_LIMITS.read_text()
    assert "check_telegram_rate_limits" in source
    assert "TELEGRAM_CHAT_RATE" in source
    assert "TELEGRAM_GROUP_RATE" in source
    assert "TELEGRAM_GLOBAL_RATE" in source


def test_rate_limiter_uses_telegram_constants() -> None:
    """Telegram rate limits must match official docs."""
    source = RATE_LIMITS.read_text()
    # 1 message/sec per chat
    assert "1.0" in source
    # 20 messages/min per group (20/60 = 0.333...)
    assert "20.0" in source
    # 30 messages/sec global
    assert "30.0" in source


def test_worker_process_imports_delivery_sender() -> None:
    """worker.py must import DeliverySender."""
    source = WORKER_PROCESS.read_text()
    assert "DeliverySender" in source
    assert "from app.services.delivery_sender" in source


def test_worker_process_imports_rate_limiter() -> None:
    """worker.py must import RateLimiter from rate_limits."""
    source = WORKER_PROCESS.read_text()
    assert "RateLimiter" in source
    assert "from app.services.rate_limits" in source


def test_worker_process_creates_rate_limiter() -> None:
    """worker.py must create shared RateLimiter instance."""
    source = WORKER_PROCESS.read_text()
    assert "_rate_limiter" in source
    assert "RateLimiter()" in source


def test_worker_process_passes_rate_limiter() -> None:
    """worker.py must pass rate_limiter to DeliverySender."""
    source = WORKER_PROCESS.read_text()
    assert "rate_limiter=self._rate_limiter" in source


def test_delivery_sender_uses_rate_limiter() -> None:
    """DeliverySender must accept and use rate_limiter parameter."""
    source = DELIVERY_SENDER.read_text()
    assert "rate_limiter" in source
    assert "self._rate_limiter" in source
