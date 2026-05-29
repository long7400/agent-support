from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from core.api.schemas.messages import (
    InboundMessageEnvelope,
    MessageDirection,
    Platform,
    StreamMessageEnvelope,
)
from core.config import Settings, get_settings
from core.persistence.repositories.chat_events import ChatEventRepository
from core.services.platforms import TenantPlatformService


class PlatformResolverProtocol(Protocol):
    def resolve_active(
        self,
        *,
        platform: Platform,
        external_workspace_id: str,
        external_channel_id: str,
    ) -> Any: ...


class ChatEventRepositoryProtocol(Protocol):
    def insert_inbound_idempotent(
        self,
        *,
        tenant_id: UUID,
        trace_id: UUID,
        platform: Platform,
        channel_id: str,
        user_id: str,
        message_id: str,
        text: str,
        thread_id: str | None,
    ) -> tuple[bool, Any]: ...


@dataclass(frozen=True)
class MessageIngestResult:
    created: bool
    chat_event_id: UUID
    stream_message: StreamMessageEnvelope


class MessageIngestService:
    def __init__(
        self,
        *,
        platform_service: PlatformResolverProtocol,
        chat_events: ChatEventRepositoryProtocol,
        settings: Settings | None = None,
    ) -> None:
        self.platform_service = platform_service
        self.chat_events = chat_events
        self.settings = settings or get_settings()

    @classmethod
    def from_session(cls, session: Any) -> MessageIngestService:
        return cls(
            platform_service=TenantPlatformService.from_session(session),
            chat_events=ChatEventRepository(session),
        )

    def ingest_inbound_message(self, message: InboundMessageEnvelope) -> MessageIngestResult:
        platform_mapping = self.platform_service.resolve_active(
            platform=message.platform,
            external_workspace_id=message.external_workspace_id,
            external_channel_id=message.channel_id,
        )
        tenant_id = _tenant_id(platform_mapping)
        return TrustedMessageIngestService(
            chat_events=self.chat_events,
            settings=self.settings,
        ).ingest_inbound_message(message, tenant_id=tenant_id)


class TrustedMessageIngestService:
    def __init__(
        self,
        *,
        chat_events: ChatEventRepositoryProtocol,
        settings: Settings | None = None,
    ) -> None:
        self.chat_events = chat_events
        self.settings = settings or get_settings()

    @classmethod
    def from_session(cls, session: Any) -> TrustedMessageIngestService:
        return cls(chat_events=ChatEventRepository(session))

    def ingest_inbound_message(
        self,
        message: InboundMessageEnvelope,
        *,
        tenant_id: UUID,
    ) -> MessageIngestResult:
        created, chat_event = self.chat_events.insert_inbound_idempotent(
            tenant_id=tenant_id,
            trace_id=message.trace_id,
            platform=message.platform,
            channel_id=message.channel_id,
            user_id=message.user_id,
            message_id=message.message_id,
            text=message.text,
            thread_id=message.thread_id,
        )
        chat_event_id = _chat_event_id(chat_event)
        return MessageIngestResult(
            created=created,
            chat_event_id=chat_event_id,
            stream_message=StreamMessageEnvelope(
                trace_id=message.trace_id,
                tenant_id=tenant_id,
                chat_event_id=chat_event_id,
                direction=MessageDirection.INBOUND,
                platform=message.platform,
                channel_id=message.channel_id,
                user_id=message.user_id,
                message_id=message.message_id,
                text_preview=message.text[: self.settings.redis_text_preview_max_chars],
            ),
        )


def tenant_id_from_platform_mapping(resource: Any) -> UUID:
    value = resource["tenant_id"] if isinstance(resource, dict) else resource.tenant_id
    if isinstance(value, UUID):
        return value
    raise TypeError("tenant platform tenant_id must be a UUID")


def _tenant_id(resource: Any) -> UUID:
    return tenant_id_from_platform_mapping(resource)


def _chat_event_id(resource: Any) -> UUID:
    value = resource["id"] if isinstance(resource, dict) else resource.id
    if isinstance(value, UUID):
        return value
    raise TypeError("chat event id must be a UUID")
