"""Discord mock adapter — proves adapter contracts are platform-neutral.

This module exists to verify that NormalizedInboundEvent and
OutboundDeliveryEnvelope can be produced and consumed without
referencing Telegram-specific field names.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.schemas.adapter import (
    DeliveryAction,
    MessageDirection,
    MessageType,
    NormalizedInboundEvent,
    OutboundDeliveryEnvelope,
    Platform,
    TEXT_PREVIEW_MAX_LENGTH,
)


def normalize_discord_message(
    message: dict[str, Any],
    external_workspace_id: str | None = None,
) -> NormalizedInboundEvent:
    """Convert a mock Discord message dict into a NormalizedInboundEvent.

    Args:
        message: Dict with keys: id, channel_id, guild_id, author.id, content,
                 timestamp, type.
        external_workspace_id: Guild ID or workspace identifier.

    Returns:
        NormalizedInboundEvent with platform='discord'.

    Raises:
        ValueError: If required fields are missing.
    """
    message_id = message.get("id")
    if not message_id:
        raise ValueError("Missing id in Discord message")

    channel_id = message.get("channel_id")
    if not channel_id:
        raise ValueError("Missing channel_id in Discord message")

    author = message.get("author", {})
    sender_id = str(author["id"]) if "id" in author else None

    content = message.get("content")
    text_preview = content[:TEXT_PREVIEW_MAX_LENGTH] if content and len(content) > TEXT_PREVIEW_MAX_LENGTH else content

    # Determine message type
    content_str = content or ""
    if content_str.startswith("!") or content_str.startswith("/"):
        msg_type = MessageType.COMMAND
    elif message.get("attachments"):
        msg_type = MessageType.MEDIA
    elif message.get("type") == 7:  # USER_JOIN system message
        msg_type = MessageType.SYSTEM
    else:
        msg_type = MessageType.TEXT

    # Timestamp
    ts = message.get("timestamp")
    occurred_at = None
    if ts:
        try:
            occurred_at = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            occurred_at = None

    metadata: dict[str, Any] = {
        "discord_message_type": message.get("type", 0),
    }

    return NormalizedInboundEvent(
        platform=Platform.DISCORD,
        external_message_id=f"discord:msg:{message_id}",
        external_channel_id=str(channel_id),
        external_thread_id=str(message.get("thread_id")) if message.get("thread_id") else None,
        external_workspace_id=external_workspace_id or str(message.get("guild_id"))
        if message.get("guild_id")
        else None,
        external_user_id=sender_id,
        message_type=msg_type,
        direction=MessageDirection.INBOUND,
        text_preview=text_preview,
        metadata=metadata,
        occurred_at=occurred_at,
    )


def build_discord_delivery_envelope(
    *,
    tenant_id: Any,
    channel_id: Any,
    text: str,
    idempotency_key: str,
) -> OutboundDeliveryEnvelope:
    """Build a Discord delivery envelope for contract testing."""
    return OutboundDeliveryEnvelope(
        tenant_id=tenant_id,
        platform=Platform.DISCORD,
        channel_id=channel_id,
        action=DeliveryAction.SEND_MESSAGE,
        text_content=text,
        idempotency_key=idempotency_key,
    )
