"""Discord mock adapter contract tests.

Proves that NormalizedInboundEvent and OutboundDeliveryEnvelope can be
produced and consumed without referencing Telegram-specific field names.
"""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.adapter import (
    DeliveryAction,
    MessageDirection,
    MessageType,
    NormalizedInboundEvent,
    OutboundDeliveryEnvelope,
    Platform,
    TEXT_PREVIEW_MAX_LENGTH,
)
from app.services.discord_mock_adapter import (
    build_discord_delivery_envelope,
    normalize_discord_message,
)


class TestNormalizedInboundEventHasNoTenantId:
    """Critical: inbound schema must not allow tenant_id."""

    def test_tenant_id_rejected_in_inbound_event(self) -> None:
        """Test that tenant_id is rejected in NormalizedInboundEvent."""
        with pytest.raises(ValidationError, match="tenant_id"):
            NormalizedInboundEvent(
                platform=Platform.DISCORD,
                external_message_id="discord:msg:123",
                external_channel_id="ch_456",
                message_type=MessageType.TEXT,
                tenant_id=uuid4(),  # type: ignore[call-arg]
            )

    def test_extra_fields_forbidden(self) -> None:
        """Test that extra fields are forbidden in NormalizedInboundEvent."""
        with pytest.raises(ValidationError, match="Extra inputs"):
            NormalizedInboundEvent(
                platform=Platform.DISCORD,
                external_message_id="discord:msg:123",
                external_channel_id="ch_456",
                message_type=MessageType.TEXT,
                secret_token="should_be_rejected",  # type: ignore[call-arg]
            )


class TestDiscordNormalization:
    """Discord messages normalize through the same contract."""

    def test_basic_text_message(self) -> None:
        """Test normalization of basic text message."""
        event = normalize_discord_message(
            {
                "id": "100001",
                "channel_id": "200001",
                "guild_id": "300001",
                "author": {"id": "400001"},
                "content": "Hello world",
                "timestamp": "2026-06-06T12:00:00Z",
                "type": 0,
            }
        )
        assert event.platform == Platform.DISCORD
        assert event.external_message_id == "discord:msg:100001"
        assert event.external_channel_id == "200001"
        assert event.external_workspace_id == "300001"
        assert event.external_user_id == "400001"
        assert event.message_type == MessageType.TEXT
        assert event.text_preview == "Hello world"
        assert event.direction == MessageDirection.INBOUND

    def test_command_message(self) -> None:
        """Test normalization of command message."""
        event = normalize_discord_message(
            {
                "id": "100002",
                "channel_id": "200001",
                "author": {"id": "400001"},
                "content": "!help",
                "type": 0,
            }
        )
        assert event.message_type == MessageType.COMMAND

    def test_media_message(self) -> None:
        """Test normalization of media message."""
        event = normalize_discord_message(
            {
                "id": "100003",
                "channel_id": "200001",
                "author": {"id": "400001"},
                "content": "Check this out",
                "attachments": [{"url": "https://example.com/image.png"}],
                "type": 0,
            }
        )
        assert event.message_type == MessageType.MEDIA

    def test_system_message(self) -> None:
        """Test normalization of system message."""
        event = normalize_discord_message(
            {
                "id": "100004",
                "channel_id": "200001",
                "author": {"id": "400001"},
                "content": "",
                "type": 7,
            }
        )
        assert event.message_type == MessageType.SYSTEM

    def test_missing_id_raises(self) -> None:
        """Test that missing id raises ValueError."""
        with pytest.raises(ValueError, match="Missing id"):
            normalize_discord_message({"channel_id": "200001", "content": "hello"})

    def test_missing_channel_id_raises(self) -> None:
        """Test that missing channel_id raises ValueError."""
        with pytest.raises(ValueError, match="Missing channel_id"):
            normalize_discord_message({"id": "100001", "content": "hello"})

    def test_text_truncation(self) -> None:
        """Test truncation of long text content."""
        long_text = "x" * (TEXT_PREVIEW_MAX_LENGTH + 500)
        event = normalize_discord_message(
            {
                "id": "100005",
                "channel_id": "200001",
                "author": {"id": "400001"},
                "content": long_text,
                "type": 0,
            }
        )
        assert event.text_preview is not None
        assert len(event.text_preview) == TEXT_PREVIEW_MAX_LENGTH

    def test_no_tenant_id_in_output(self) -> None:
        """Test that tenant_id is not present in normalized event."""
        event = normalize_discord_message(
            {
                "id": "100006",
                "channel_id": "200001",
                "author": {"id": "400001"},
                "content": "test",
                "type": 0,
            }
        )
        event_dict = event.model_dump()
        assert "tenant_id" not in event_dict


class TestOutboundDeliveryEnvelope:
    """Outbound envelopes carry trusted tenant_id."""

    def test_build_discord_delivery(self) -> None:
        """Test building Discord delivery envelope."""
        tid = uuid4()
        cid = uuid4()
        envelope = build_discord_delivery_envelope(
            tenant_id=tid,
            channel_id=cid,
            text="Hello from Discord mock",
            idempotency_key="idem-123",
        )
        assert envelope.platform == Platform.DISCORD
        assert envelope.tenant_id == tid
        assert envelope.action == DeliveryAction.SEND_MESSAGE
        assert envelope.text_content == "Hello from Discord mock"
        assert envelope.idempotency_key == "idem-123"

    def test_extra_fields_forbidden_in_envelope(self) -> None:
        """Test that extra fields are forbidden in OutboundDeliveryEnvelope."""
        with pytest.raises(ValidationError, match="Extra inputs"):
            OutboundDeliveryEnvelope(
                tenant_id=uuid4(),
                platform=Platform.DISCORD,
                channel_id=uuid4(),
                action=DeliveryAction.SEND_MESSAGE,
                idempotency_key="key-1",
                raw_body="should_not_be_here",  # type: ignore[call-arg]
            )


class TestContractNoTelegramDependencies:
    """Verify contracts don't depend on Telegram-specific field names."""

    def test_discord_normalizer_does_not_reference_telegram_keys(self) -> None:
        """Discord adapter source should not contain Telegram-specific field names."""
        import inspect

        source = inspect.getsource(normalize_discord_message)
        telegram_keys = ["update_id", "chat_id", "message_thread_id", "my_chat_member"]
        for key in telegram_keys:
            assert key not in source, f"Discord adapter references Telegram key: {key}"
