"""P2 platform ingest/delivery integration guardrails.

These source-backed tests pin the DB smoke path until a Docker-backed CI
fixture is available: webhook ingest -> processing outbox -> delivery sender
-> delivery receipt, plus duplicate and audit branches.
"""

from pathlib import Path

WEBHOOKS = Path("app/api/v1/platform_webhooks.py")
INGEST = Path("app/services/platform_ingest.py")
OUTBOX_WORKER = Path("app/services/outbox_worker.py")
DELIVERY_SENDER = Path("app/services/delivery_sender.py")


def test_integration_path_webhook_to_processing_to_delivery_receipt() -> None:
    """The end-to-end path must wire accepted webhook rows through receipt creation."""
    webhook_source = WEBHOOKS.read_text()
    ingest_source = INGEST.read_text()
    worker_source = OUTBOX_WORKER.read_text()
    delivery_source = DELIVERY_SENDER.read_text()

    assert "normalize_telegram_update" in webhook_source
    assert "ingest_event" in webhook_source
    assert "ChatEvent" in ingest_source and "ProcessingOutbox" in ingest_source
    assert "NOTIFY outbox_new" in ingest_source
    assert "DeliveryOutbox(" in worker_source
    assert "DeliveryReceipt(" in delivery_source
    assert 'delivery.status = "delivered"' in delivery_source


def test_integration_duplicate_webhook_is_accepted_idempotently() -> None:
    """Duplicate inbound events must be accepted without creating duplicate work."""
    webhook_source = WEBHOOKS.read_text()
    ingest_source = INGEST.read_text()

    assert "DuplicateAcceptedError" in webhook_source
    assert '"duplicate": "true"' in webhook_source
    assert "IntegrityError" in ingest_source
    assert "DuplicateAcceptedError" in ingest_source


def test_integration_unknown_channel_and_scope_failures_are_audited() -> None:
    """Fail-closed ingest branches must leave durable audit events."""
    webhook_source = WEBHOOKS.read_text()
    adapter_source = Path("app/api/v1/adapter_ingest.py").read_text()

    assert 'action="unknown_channel_rejected"' in webhook_source
    assert 'action="scope_mismatch_rejected"' in adapter_source
    assert "emit_audit_event" in webhook_source
    assert "emit_audit_event" in adapter_source


def test_integration_retry_dlq_and_platform_auth_audit_paths_exist() -> None:
    """Worker retry/DLQ and platform auth failure paths must be auditable."""
    worker_source = OUTBOX_WORKER.read_text()
    delivery_source = DELIVERY_SENDER.read_text()

    assert 'action="processing_retry_scheduled"' in worker_source
    assert 'action="processing_dlq"' in worker_source
    assert 'action="delivery_retry_scheduled"' in delivery_source
    assert 'action="delivery_dlq"' in delivery_source
    assert 'action="delivery_platform_auth_failed"' in delivery_source
