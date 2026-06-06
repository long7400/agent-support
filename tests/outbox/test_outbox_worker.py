"""Outbox worker guardrail tests (Task 7).

Source-based tests verifying the processing outbox worker implements
required patterns: SKIP LOCKED, claim/retry/DLQ, backoff, stale reclaim.
"""

from pathlib import Path

OUTBOX_WORKER = Path("app/services/outbox_worker.py")
WORKER_PROCESS = Path("app/worker.py")


def test_outbox_worker_uses_skip_locked() -> None:
    """claim_batch must use FOR UPDATE SKIP LOCKED for safe concurrent claiming."""
    source = OUTBOX_WORKER.read_text()
    assert "FOR UPDATE SKIP LOCKED" in source
    assert "claim_batch" in source


def test_outbox_worker_claims_pending_only() -> None:
    """claim_batch must filter for status='pending' and run_after_ts <= now."""
    source = OUTBOX_WORKER.read_text()
    assert "status = 'pending'" in source
    assert "run_after_ts <=" in source
    assert "dead_letter = false" in source


def test_outbox_worker_sets_processing_status() -> None:
    """claim_batch must mark claimed rows as 'processing' with worker_id."""
    source = OUTBOX_WORKER.read_text()
    assert "status = 'processing'" in source
    assert "worker_id" in source
    assert "heartbeat_at" in source


def test_outbox_worker_orders_by_created_at() -> None:
    """claim_batch must order by created_at ASC for FIFO processing."""
    source = OUTBOX_WORKER.read_text()
    assert "ORDER BY created_at ASC" in source


def test_outbox_worker_reclaims_stale() -> None:
    """reclaim_stale must detect and reset stuck processing rows."""
    source = OUTBOX_WORKER.read_text()
    assert "reclaim_stale" in source
    assert "stale_cutoff" in source or "stale_after" in source
    assert 'status == "processing"' in source
    assert "heartbeat_at <" in source


def test_outbox_worker_implements_backoff() -> None:
    """compute_backoff must implement exponential backoff with cap."""
    source = OUTBOX_WORKER.read_text()
    assert "compute_backoff" in source
    assert "2**" in source or "2 **" in source  # exponential
    assert "RETRY_BACKOFF_MAX_SECONDS" in source
    assert "RETRY_BACKOFF_BASE_SECONDS" in source


def test_outbox_worker_moves_to_dlq() -> None:
    """schedule_retry must move to dead_letter after max retries."""
    source = OUTBOX_WORKER.read_text()
    assert "dead_letter" in source
    assert "RETRY_MAX_ATTEMPTS" in source
    assert "schedule_retry" in source
    assert "dlq" in source.lower()


def test_outbox_worker_creates_delivery_outbox() -> None:
    """process_row must create delivery_outbox rows (Phase 2 stub)."""
    source = OUTBOX_WORKER.read_text()
    assert "DeliveryOutbox" in source
    assert "idempotency_key" in source
    assert "process_row" in source


def test_outbox_worker_marks_done() -> None:
    """process_row must mark processing row as 'done' after delivery creation."""
    source = OUTBOX_WORKER.read_text()
    # Must set status to done after processing
    assert '"done"' in source


def test_outbox_worker_checks_delivery_idempotency() -> None:
    """process_row must check for existing delivery before creating new one."""
    source = OUTBOX_WORKER.read_text()
    # Must check existing delivery_outbox by idempotency_key
    assert "idempotency_key" in source
    assert "existing" in source


def test_outbox_worker_uses_tenant_context() -> None:
    """run_cycle must process rows within tenant context."""
    source = OUTBOX_WORKER.read_text()
    assert "with_tenant_context" in source


def test_outbox_worker_handles_errors() -> None:
    """run_cycle must catch exceptions and schedule retries."""
    source = OUTBOX_WORKER.read_text()
    assert "except Exception" in source
    assert "schedule_retry" in source


def test_processing_worker_audits_retry_scheduled() -> None:
    """Processing retries must be persisted as audit events, not only logged."""
    source = OUTBOX_WORKER.read_text()
    assert "processing_retry_scheduled" in source
    assert "await emit_audit_event" in source
    assert 'action="processing_retry_scheduled"' in source


def test_outbox_worker_bounds_error_messages() -> None:
    """Error messages stored in last_error must be bounded."""
    source = OUTBOX_WORKER.read_text()
    # Check that error strings are truncated
    assert "[:1000]" in source or "[:500]" in source


def test_outbox_worker_discovers_tenants() -> None:
    """get_tenants_with_pending_processing must scan for work across tenants."""
    source = OUTBOX_WORKER.read_text()
    assert "get_tenants_with_pending_processing" in source
    assert "distinct" in source.lower() or ".distinct()" in source


def test_outbox_worker_logs_without_secrets() -> None:
    """Worker logs must not include raw secrets or sensitive data."""
    source = OUTBOX_WORKER.read_text()
    # Should log structured events, not raw data
    assert "logger.info" in source
    assert "logger.warning" in source
    # Must not log bot tokens or raw payloads
    assert "bot_token" not in source
    assert "raw_payload" not in source
    assert "secret" not in source.lower() or "webhook_secret" not in source.lower()


def test_worker_process_imports_outbox_worker() -> None:
    """worker.py must import ProcessingOutboxWorker."""
    source = WORKER_PROCESS.read_text()
    assert "ProcessingOutboxWorker" in source
    assert "from app.services.outbox_worker" in source


def test_worker_process_supports_roles() -> None:
    """worker.py must support role-based processing and delivery."""
    source = WORKER_PROCESS.read_text()
    assert "WORKER_ROLE" in source
    assert "processing" in source
    assert "delivery" in source


def test_worker_process_uses_session_local() -> None:
    """worker.py must use AsyncSessionLocal for DB sessions."""
    source = WORKER_PROCESS.read_text()
    assert "AsyncSessionLocal" in source


def test_worker_process_has_graceful_shutdown() -> None:
    """worker.py must support graceful shutdown via signal handlers."""
    source = WORKER_PROCESS.read_text()
    assert "signal" in source
    assert "request_stop" in source or "_stop_event" in source
