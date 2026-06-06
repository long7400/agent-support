"""Telegram adapter: normalize raw Telegram Update JSON into NormalizedInboundEvent."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.schemas.adapter import (
    MessageDirection,
    MessageType,
    NormalizedInboundEvent,
    Platform,
    TEXT_PREVIEW_MAX_LENGTH,
)


def _classify_message_type(text: str | None) -> MessageType:
    """Classify message type based on text content."""
    if text and text.startswith("/"):
        return MessageType.COMMAND
    return MessageType.TEXT


def _truncate_text(text: str | None, max_length: int = TEXT_PREVIEW_MAX_LENGTH) -> str | None:
    """Truncate text to max_length, adding ellipsis if truncated."""
    if text is None:
        return None
    if len(text) <= max_length:
        return text
    return text[: max_length - 1] + "…"


def _build_external_message_id(update_id: int, message_id: int | None, is_edit: bool = False) -> str:
    """Build a deterministic external message ID from Telegram fields."""
    suffix = ":edit" if is_edit else ""
    if message_id is not None:
        return f"tg:msg:{message_id}{suffix}"
    return f"tg:update:{update_id}{suffix}"


def _extract_message_payload(update: dict[str, Any]) -> tuple[str, dict[str, Any] | None, bool]:
    """Extract the message-like payload from a Telegram Update.

    Returns (update_type, message_dict, is_edit).
    Checks in priority order: message, edited_message, channel_post,
    edited_channel_post, my_chat_member.
    """
    if "message" in update:
        return "message", update["message"], False
    if "edited_message" in update:
        return "edited_message", update["edited_message"], True
    if "channel_post" in update:
        return "channel_post", update["channel_post"], False
    if "edited_channel_post" in update:
        return "edited_channel_post", update["edited_channel_post"], True
    if "my_chat_member" in update:
        return "my_chat_member", update["my_chat_member"], False
    return "unknown", None, False


def normalize_telegram_update(
    update: dict[str, Any],
    external_workspace_id: str | None = None,
) -> NormalizedInboundEvent:
    """Convert a raw Telegram Update dict into a NormalizedInboundEvent.

    Args:
        update: Raw Telegram Update JSON (dict).
        external_workspace_id: Bot ID or workspace identifier from trusted context.

    Returns:
        NormalizedInboundEvent with platform='telegram'.

    Raises:
        ValueError: If the update cannot be normalized.
    """
    update_id = update.get("update_id")
    if update_id is None:
        raise ValueError("Missing update_id in Telegram update")

    update_type, message, is_edit = _extract_message_payload(update)

    if message is None:
        raise ValueError(f"Unsupported Telegram update type: {update_type}")

    # Extract chat info
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    if chat_id is None:
        raise ValueError("Missing chat.id in Telegram message")

    # Extract message ID
    message_id = message.get("message_id")

    # Extract sender
    from_user = message.get("from", {})
    sender_id = str(from_user["id"]) if "id" in from_user else None

    # Extract text
    text = message.get("text") or message.get("caption")
    truncated_text = _truncate_text(text)

    # Determine message type
    if is_edit:
        msg_type = MessageType.EDITED
    elif update_type == "my_chat_member":
        msg_type = MessageType.SYSTEM
    elif message.get("photo") or message.get("video") or message.get("document") or message.get("audio"):
        msg_type = MessageType.MEDIA
    else:
        msg_type = _classify_message_type(text)

    # Thread ID (forum/topic)
    thread_id = message.get("message_thread_id")
    external_thread_id = str(thread_id) if thread_id is not None else None

    # Build metadata (bounded, no raw payload)
    metadata: dict[str, Any] = {
        "update_type": update_type,
        "chat_type": chat.get("type"),
    }
    if message.get("reply_to_message", {}).get("message_id"):
        metadata["reply_to_message_id"] = message["reply_to_message"]["message_id"]

    # Timestamp
    date_val = message.get("date")
    occurred_at = datetime.fromtimestamp(date_val, tz=timezone.utc) if date_val else None

    return NormalizedInboundEvent(
        platform=Platform.TELEGRAM,
        external_message_id=_build_external_message_id(update_id, message_id, is_edit),
        external_channel_id=str(chat_id),
        external_thread_id=external_thread_id,
        external_workspace_id=external_workspace_id,
        external_user_id=sender_id,
        message_type=msg_type,
        direction=MessageDirection.INBOUND,
        text_preview=truncated_text,
        metadata=metadata,
        occurred_at=occurred_at,
    )
