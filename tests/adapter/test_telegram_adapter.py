"""Telegram adapter normalization tests."""

from datetime import timezone

import pytest

from app.schemas.adapter import (
    MessageDirection,
    MessageType,
    Platform,
    TEXT_PREVIEW_MAX_LENGTH,
)
from app.services.telegram_adapter import normalize_telegram_update


def _base_message(
    *,
    chat_id: int = -1001234567890,
    message_id: int = 42,
    user_id: int = 100001,
    text: str = "Hello world",
    date: int = 1749218400,
) -> dict:
    return {
        "message_id": message_id,
        "chat": {"id": chat_id, "type": "group"},
        "from": {"id": user_id, "first_name": "Test"},
        "text": text,
        "date": date,
    }


class TestTelegramNormalization:
    """Telegram Update → NormalizedInboundEvent."""

    def test_basic_text_message(self) -> None:
        """Test normalization of basic text message."""
        update = {"update_id": 1, "message": _base_message()}
        event = normalize_telegram_update(update, external_workspace_id="bot_123")

        assert event.platform == Platform.TELEGRAM
        assert event.external_message_id == "tg:msg:42"
        assert event.external_channel_id == "-1001234567890"
        assert event.external_workspace_id == "bot_123"
        assert event.external_user_id == "100001"
        assert event.message_type == MessageType.TEXT
        assert event.direction == MessageDirection.INBOUND
        assert event.text_preview == "Hello world"

    def test_command_message(self) -> None:
        """Test normalization of command message."""
        update = {"update_id": 2, "message": _base_message(text="/start")}
        event = normalize_telegram_update(update)
        assert event.message_type == MessageType.COMMAND

    def test_edited_message(self) -> None:
        """Test normalization of edited message."""
        update = {"update_id": 3, "edited_message": _base_message(text="edited")}
        event = normalize_telegram_update(update)
        assert event.message_type == MessageType.EDITED
        assert event.external_message_id == "tg:msg:42:edit"

    def test_channel_post(self) -> None:
        """Test normalization of channel post."""
        update = {"update_id": 4, "channel_post": _base_message(chat_id=-1009999999999, text="channel post")}
        event = normalize_telegram_update(update)
        assert event.platform == Platform.TELEGRAM
        assert event.external_channel_id == "-1009999999999"
        assert event.message_type == MessageType.TEXT

    def test_edited_channel_post(self) -> None:
        """Test normalization of edited channel post."""
        update = {"update_id": 5, "edited_channel_post": _base_message(text="edited post")}
        event = normalize_telegram_update(update)
        assert event.message_type == MessageType.EDITED

    def test_my_chat_member_is_system(self) -> None:
        """Test normalization of my_chat_member event as system message."""
        update = {
            "update_id": 6,
            "my_chat_member": {
                "message_id": 99,
                "chat": {"id": -1001111111111, "type": "group"},
                "from": {"id": 100001},
                "date": 1749218400,
                "old_chat_member": {"status": "left"},
                "new_chat_member": {"status": "member"},
            },
        }
        event = normalize_telegram_update(update)
        assert event.message_type == MessageType.SYSTEM

    def test_media_message(self) -> None:
        """Test normalization of media message."""
        msg = _base_message(text=None)
        msg["photo"] = [{"file_id": "abc123"}]
        update = {"update_id": 7, "message": msg}
        event = normalize_telegram_update(update)
        assert event.message_type == MessageType.MEDIA

    def test_caption_as_text_fallback(self) -> None:
        """Test caption used as text fallback when text is missing."""
        msg = _base_message(text=None)
        msg["caption"] = "Photo caption"
        msg["photo"] = [{"file_id": "abc123"}]
        update = {"update_id": 8, "message": msg}
        event = normalize_telegram_update(update)
        assert event.text_preview == "Photo caption"

    def test_missing_text(self) -> None:
        """Test handling of message with no text or caption."""
        msg = _base_message(text=None)
        del msg["text"]
        update = {"update_id": 9, "message": msg}
        event = normalize_telegram_update(update)
        assert event.text_preview is None
        assert event.message_type == MessageType.TEXT  # no text, default TEXT

    def test_large_text_truncation(self) -> None:
        """Test truncation of large text content."""
        long_text = "a" * (TEXT_PREVIEW_MAX_LENGTH + 1000)
        update = {"update_id": 10, "message": _base_message(text=long_text)}
        event = normalize_telegram_update(update)
        assert event.text_preview is not None
        assert len(event.text_preview) == TEXT_PREVIEW_MAX_LENGTH
        assert event.text_preview.endswith("…")

    def test_missing_update_id_raises(self) -> None:
        """Test error handling for missing update_id."""
        with pytest.raises(ValueError, match="Missing update_id"):
            normalize_telegram_update({"message": _base_message()})

    def test_unsupported_update_type_raises(self) -> None:
        """Test error handling for unsupported update type."""
        with pytest.raises(ValueError, match="Unsupported"):
            normalize_telegram_update({"update_id": 100, "poll": {"id": "x"}})

    def test_missing_chat_id_raises(self) -> None:
        """Test error handling for missing chat.id."""
        msg = _base_message()
        del msg["chat"]["id"]
        with pytest.raises(ValueError, match="Missing chat.id"):
            normalize_telegram_update({"update_id": 11, "message": msg})

    def test_thread_id_extracted(self) -> None:
        """Test extraction of thread ID from message_thread_id."""
        msg = _base_message()
        msg["message_thread_id"] = 555
        update = {"update_id": 12, "message": msg}
        event = normalize_telegram_update(update)
        assert event.external_thread_id == "555"

    def test_occurred_at_parsed(self) -> None:
        """Test parsing of occurred_at timestamp."""
        update = {"update_id": 13, "message": _base_message(date=1749218400)}
        event = normalize_telegram_update(update)
        assert event.occurred_at is not None
        assert event.occurred_at.tzinfo == timezone.utc

    def test_reply_metadata_captured(self) -> None:
        """Test capture of reply metadata."""
        msg = _base_message()
        msg["reply_to_message"] = {"message_id": 41}
        update = {"update_id": 14, "message": msg}
        event = normalize_telegram_update(update)
        assert event.metadata.get("reply_to_message_id") == 41

    def test_metadata_is_bounded(self) -> None:
        """Metadata must not contain raw payload or unbounded fields."""
        update = {"update_id": 15, "message": _base_message()}
        event = normalize_telegram_update(update)
        # Metadata keys should be controlled
        assert "update_type" in event.metadata
        assert "chat_type" in event.metadata
        # No raw message dict in metadata
        assert "raw_message" not in event.metadata

    def test_no_tenant_id_in_output(self) -> None:
        """Test that tenant_id is not present in normalized event."""
        update = {"update_id": 16, "message": _base_message()}
        event = normalize_telegram_update(update)
        event_dict = event.model_dump()
        assert "tenant_id" not in event_dict
