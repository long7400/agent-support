"""Adapter contract schemas — platform-neutral types for inbound/outbound messaging."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Platform(StrEnum):
    """Supported platform types."""

    TELEGRAM = "telegram"
    DISCORD = "discord"


class MessageDirection(StrEnum):
    """Message flow direction."""

    INBOUND = "inbound"
    OUTBOUND = "outbound"


class MessageType(StrEnum):
    """Normalized message types."""

    TEXT = "text"
    COMMAND = "command"
    MEDIA = "media"
    SYSTEM = "system"
    EDITED = "edited"


class DeliveryAction(StrEnum):
    """Outbound delivery actions."""

    SEND_MESSAGE = "send_message"
    EDIT_MESSAGE = "edit_message"
    DELETE_MESSAGE = "delete_message"


class ReceiptStatus(StrEnum):
    """Delivery receipt outcomes."""

    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"


# Max text length for normalized previews
TEXT_PREVIEW_MAX_LENGTH = 4000


class AdapterPrincipal(BaseModel):
    """Authenticated adapter identity.

    Constructed after trusted credential lookup. Tenant ID is set only
    after the credential has been validated against DB state.
    """

    model_config = ConfigDict(frozen=True)

    adapter_credential_id: UUID
    platform: Platform
    name: str = Field(..., max_length=200)
    credential_prefix: str = Field(..., max_length=32)
    allowed_channel_patterns: tuple[str, ...] = Field(default_factory=tuple)
    scopes: tuple[str, ...] = Field(default_factory=tuple)
    tenant_id: UUID | None = Field(default=None, description="Set only after trusted lookup")
    status: str = Field(default="active", max_length=32)

    def is_active(self) -> bool:
        """Check if the principal has active status."""
        return self.status == "active"

    def has_scope(self, scope: str) -> bool:
        """Check if the principal has the specified scope."""
        return scope in self.scopes

    def is_channel_allowed(self, channel_id: str) -> bool:
        """Check if the principal can access the specified channel."""
        if not self.allowed_channel_patterns:
            return True
        return any(
            channel_id == pattern or channel_id.startswith(pattern.rstrip("*"))
            for pattern in self.allowed_channel_patterns
        )


class NormalizedInboundEvent(BaseModel):
    """Platform-neutral inbound event.

    IMPORTANT: This schema must NEVER contain a tenant_id field.
    Tenant identity is resolved server-side via trusted DB lookup only.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    platform: Platform
    external_message_id: str = Field(..., min_length=1, max_length=256)
    external_channel_id: str = Field(..., min_length=1, max_length=256)
    external_thread_id: str | None = Field(default=None, max_length=256)
    external_workspace_id: str | None = Field(default=None, max_length=256)
    external_user_id: str | None = Field(default=None, max_length=256)
    message_type: MessageType
    direction: MessageDirection = Field(default=MessageDirection.INBOUND)
    text_preview: str | None = Field(default=None, max_length=TEXT_PREVIEW_MAX_LENGTH)
    metadata: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime | None = None


class OutboundDeliveryEnvelope(BaseModel):
    """Platform-neutral outbound delivery request.

    Tenant ID is set from trusted server-side state, not from request body.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    tenant_id: UUID
    platform: Platform
    channel_id: UUID
    thread_id: UUID | None = None
    action: DeliveryAction
    text_content: str | None = Field(default=None, max_length=TEXT_PREVIEW_MAX_LENGTH)
    metadata: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = Field(..., min_length=1, max_length=256)
    agent_run_id: UUID | None = None
