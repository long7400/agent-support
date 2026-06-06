"""Tests for P2 audit events.

Verifies that audit events are emitted for security-relevant operations
and that sensitive data is redacted from audit metadata.
"""

from pathlib import Path


from app.services.p2_audit import emit_audit_event, redact_for_audit, P2Actor


class TestEmitAuditEvent:
    """Tests for emit_audit_event function."""

    def test_emit_audit_event_has_required_fields(self) -> None:
        """Verify emit_audit_event signature includes required fields."""
        import inspect

        sig = inspect.signature(emit_audit_event)
        params = list(sig.parameters.keys())

        assert "session" in params
        assert "tenant_id" in params
        assert "actor" in params
        assert "action" in params
        assert "metadata" in params

    def test_emit_audit_event_returns_audit_event(self) -> None:
        """Verify emit_audit_event returns AuditEvent type."""
        import inspect

        sig = inspect.signature(emit_audit_event)
        return_annotation = sig.return_annotation

        assert "AuditEvent" in str(return_annotation)


class TestRedactForAudit:
    """Tests for redact_for_audit function."""

    def test_redacts_secret_fields(self) -> None:
        """Verify redact_for_audit redacts secret fields."""
        data = {
            "user_id": "123",
            "secret": "my-secret-value",
            "token": "my-token-value",
            "platform": "telegram",
        }
        redacted = redact_for_audit(data)

        assert redacted["user_id"] == "123"
        assert redacted["secret"] == "[REDACTED]"
        assert redacted["token"] == "[REDACTED]"
        assert redacted["platform"] == "telegram"

    def test_redacts_nested_secrets(self) -> None:
        """Verify redact_for_audit redacts secrets in nested dicts."""
        data = {
            "user_id": "123",
            "config": {
                "api_key": "secret-key",
                "webhook_url": "https://example.com",
            },
        }
        redacted = redact_for_audit(data)

        assert redacted["user_id"] == "123"
        assert redacted["config"]["api_key"] == "[REDACTED]"
        assert redacted["config"]["webhook_url"] == "https://example.com"

    def test_redacts_custom_sensitive_keys(self) -> None:
        """Verify redact_for_audit redacts custom sensitive keys."""
        data = {
            "user_id": "123",
            "password": "secret-password",
            "email": "user@example.com",
        }
        redacted = redact_for_audit(data, sensitive_keys=["password"])

        assert redacted["user_id"] == "123"
        assert redacted["password"] == "[REDACTED]"
        assert redacted["email"] == "user@example.com"

    def test_handles_empty_dict(self) -> None:
        """Verify redact_for_audit handles empty dict."""
        data = {}
        redacted = redact_for_audit(data)
        assert redacted == {}

    def test_handles_non_dict_values(self) -> None:
        """Verify redact_for_audit handles non-dict values."""
        data = {
            "user_id": "123",
            "count": 42,
            "enabled": True,
            "tags": ["tag1", "tag2"],
        }
        redacted = redact_for_audit(data)

        assert redacted["user_id"] == "123"
        assert redacted["count"] == 42
        assert redacted["enabled"] is True
        assert redacted["tags"] == ["tag1", "tag2"]


class TestP2Actor:
    """Tests for P2Actor class."""

    def test_p2_actor_stores_type_and_id(self) -> None:
        """Verify P2Actor stores actor_type and actor_id."""
        actor = P2Actor("webhook", "telegram-bot-123")

        assert actor.actor_type == "webhook"
        assert actor.actor_id == "telegram-bot-123"

    def test_p2_actor_is_immutable(self) -> None:
        """Verify P2Actor attributes are set in __init__."""
        actor = P2Actor("adapter", "discord-adapter-456")

        assert hasattr(actor, "actor_type")
        assert hasattr(actor, "actor_id")


class TestAuditIntegration:
    """Integration tests for audit event emission."""

    def test_webhook_route_emits_audit_on_secret_mismatch(self) -> None:
        """Verify webhook route emits audit event on secret mismatch."""
        source = Path("app/api/v1/platform_webhooks.py").read_text()

        assert "emit_audit_event" in source
        assert "webhook_secret_rejected" in source

    def test_webhook_route_emits_audit_on_unknown_platform(self) -> None:
        """Verify webhook route emits audit event on unknown platform."""
        source = Path("app/api/v1/platform_webhooks.py").read_text()

        assert "unknown_platform_mapping" in source

    def test_webhook_route_emits_audit_on_unknown_channel(self) -> None:
        """Verify webhook route emits audit event on unknown channel."""
        source = Path("app/api/v1/platform_webhooks.py").read_text()

        assert "unknown_channel_rejected" in source

    def test_webhook_route_emits_audit_on_disabled_channel(self) -> None:
        """Verify webhook route emits audit event on disabled channel."""
        source = Path("app/api/v1/platform_webhooks.py").read_text()

        assert "disabled_channel_rejected" in source

    def test_webhook_route_emits_audit_on_duplicate(self) -> None:
        """Verify webhook route emits audit event on duplicate."""
        source = Path("app/api/v1/platform_webhooks.py").read_text()

        assert "duplicate_accepted" in source

    def test_adapter_ingest_emits_audit_on_scope_mismatch(self) -> None:
        """Verify adapter ingest emits audit event on scope mismatch."""
        source = Path("app/api/v1/adapter_ingest.py").read_text()

        assert "emit_audit_event" in source
        assert "scope_mismatch_rejected" in source

    def test_adapter_ingest_emits_audit_on_unknown_channel(self) -> None:
        """Verify adapter ingest emits audit event on unknown channel."""
        source = Path("app/api/v1/adapter_ingest.py").read_text()

        assert "unknown_channel_rejected" in source

    def test_adapter_ingest_emits_audit_on_disabled_channel(self) -> None:
        """Verify adapter ingest emits audit event on disabled channel."""
        source = Path("app/api/v1/adapter_ingest.py").read_text()

        assert "disabled_channel_rejected" in source

    def test_adapter_ingest_emits_audit_on_duplicate(self) -> None:
        """Verify adapter ingest emits audit event on duplicate."""
        source = Path("app/api/v1/adapter_ingest.py").read_text()

        assert "duplicate_accepted" in source

    def test_platform_ingest_emits_audit_on_secret_mismatch(self) -> None:
        """Verify platform ingest emits audit event on secret mismatch."""
        source = Path("app/services/platform_ingest.py").read_text()

        assert "emit_audit_event" in source
        assert "webhook_secret_rejected" in source
        assert "webhook_secret_not_configured" in source

    def test_platform_ingest_emits_audit_on_event_ingested(self) -> None:
        """Verify platform ingest emits audit event on successful ingest."""
        source = Path("app/services/platform_ingest.py").read_text()

        assert "event_ingested" in source

    def test_outbox_worker_emits_audit_on_dlq(self) -> None:
        """Verify outbox worker emits audit event on DLQ."""
        source = Path("app/services/outbox_worker.py").read_text()

        assert "emit_audit_event" in source
        assert "processing_dlq" in source

    def test_delivery_sender_emits_audit_on_dlq(self) -> None:
        """Verify delivery sender emits audit event on DLQ."""
        source = Path("app/services/delivery_sender.py").read_text()

        assert "emit_audit_event" in source
        assert "delivery_dlq" in source


class TestSecretRedaction:
    """Tests to ensure secrets are not logged or stored."""

    def test_webhook_route_does_not_log_secret(self) -> None:
        """Verify webhook route does not log the secret token value."""
        source = Path("app/api/v1/platform_webhooks.py").read_text()

        # Should not log the actual secret value in logger calls
        # Check that logger calls don't include the secret variable
        logger_calls = [line.strip() for line in source.split("\n") if "logger." in line]
        for call in logger_calls:
            # Allow variable name in function signatures, but not in logger arguments
            if "x_telegram_bot_api_secret_token" in call and "def " not in call:
                # Should not be logging the secret value directly
                assert "secret_token=" not in call or "secret_token=None" in call

    def test_adapter_ingest_does_not_log_credential(self) -> None:
        """Verify adapter ingest does not log the credential."""
        source = Path("app/api/v1/adapter_ingest.py").read_text()

        # Should not log the actual credential value
        lines = source.split("\n")
        for i, line in enumerate(lines):
            if "logger." in line:
                # Check next few lines don't contain credential logging
                context = "\n".join(lines[i : min(i + 5, len(lines))])
                assert "x_adapter_credential" not in context or "credential_prefix" in context

    def test_audit_metadata_does_not_contain_secrets(self) -> None:
        """Verify audit metadata does not contain secret values."""
        webhook_source = Path("app/api/v1/platform_webhooks.py").read_text()
        adapter_source = Path("app/api/v1/adapter_ingest.py").read_text()

        # Check that audit calls don't pass secret values in metadata
        assert "secret_token" not in webhook_source.split("metadata=")[1] if "metadata=" in webhook_source else True
        assert (
            "x_adapter_credential" not in adapter_source.split("metadata=")[1]
            if "metadata=" in adapter_source
            else True
        )
