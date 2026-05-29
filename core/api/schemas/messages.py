from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from core.constants import STREAM_TEXT_PREVIEW_MAX_CHARS


class Platform(StrEnum):
    TELEGRAM = "telegram"
    DISCORD = "discord"


class MessageDirection(StrEnum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class InboundMessageEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trace_id: UUID
    platform: Platform
    external_workspace_id: str = Field(min_length=1, max_length=255)
    channel_id: str = Field(min_length=1, max_length=255)
    user_id: str = Field(min_length=1, max_length=255)
    message_id: str = Field(min_length=1, max_length=255)
    text: str = Field(min_length=1)
    thread_id: str | None = Field(default=None, max_length=255)


class StreamMessageEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trace_id: UUID
    tenant_id: UUID
    chat_event_id: UUID
    direction: MessageDirection
    platform: Platform
    channel_id: str = Field(min_length=1, max_length=255)
    user_id: str = Field(min_length=1, max_length=255)
    message_id: str = Field(min_length=1, max_length=255)
    text_preview: str = Field(max_length=STREAM_TEXT_PREVIEW_MAX_CHARS)


class OutboundMessageEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trace_id: UUID
    tenant_id: UUID
    direction: Literal[MessageDirection.OUTBOUND] = MessageDirection.OUTBOUND
    platform: Platform
    channel_id: str = Field(min_length=1, max_length=255)
    user_id: str = Field(min_length=1, max_length=255)
    reply_to_message_id: str = Field(min_length=1, max_length=255)
    inbound_chat_event_id: UUID
    text: str = Field(min_length=1, max_length=STREAM_TEXT_PREVIEW_MAX_CHARS)


class IngestAcceptedResponse(BaseModel):
    trace_id: UUID
    chat_event_id: UUID
    status: Literal["accepted"] = "accepted"
