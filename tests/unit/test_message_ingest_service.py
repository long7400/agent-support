from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from core.api.schemas.messages import InboundMessageEnvelope, MessageDirection, Platform
from core.config import Settings
from core.services.errors import ServiceError
from core.services.messages import MessageIngestService


class FakePlatformService:
    def __init__(self, tenant_id: UUID | None) -> None:
        self.tenant_id = tenant_id

    def resolve_active(
        self,
        *,
        platform: Platform,
        external_workspace_id: str,
        external_channel_id: str,
    ) -> dict[str, object]:
        del platform, external_workspace_id, external_channel_id
        if self.tenant_id is None:
            raise ServiceError(
                code="TENANT_PLATFORM_NOT_FOUND",
                message="Tenant platform mapping not found",
                status_code=404,
            )
        return {"tenant_id": self.tenant_id}


class FakeChatEventRepository:
    def __init__(self) -> None:
        self.chat_event_id = uuid4()
        self.created = True
        self.calls: list[dict[str, object]] = []

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
    ) -> tuple[bool, dict[str, object]]:
        self.calls.append(
            {
                "tenant_id": tenant_id,
                "trace_id": trace_id,
                "platform": platform,
                "channel_id": channel_id,
                "user_id": user_id,
                "message_id": message_id,
                "text": text,
                "thread_id": thread_id,
            }
        )
        return self.created, {"id": self.chat_event_id}


def inbound_message(text: str = "hello world") -> InboundMessageEnvelope:
    return InboundMessageEnvelope(
        trace_id=uuid4(),
        platform=Platform.TELEGRAM,
        external_workspace_id="workspace-a",
        channel_id="channel-a",
        user_id="user-a",
        message_id="message-a",
        text=text,
    )


def test_ingest_resolves_tenant_and_returns_stream_envelope() -> None:
    tenant_id = uuid4()
    chat_events = FakeChatEventRepository()
    service = MessageIngestService(
        platform_service=FakePlatformService(tenant_id),
        chat_events=chat_events,
        settings=Settings(redis_text_preview_max_chars=5),
    )
    message = inbound_message(text="hello world")

    result = service.ingest_inbound_message(message)

    assert result.created is True
    assert result.chat_event_id == chat_events.chat_event_id
    assert result.stream_message.tenant_id == tenant_id
    assert result.stream_message.chat_event_id == chat_events.chat_event_id
    assert result.stream_message.trace_id == message.trace_id
    assert result.stream_message.direction == MessageDirection.INBOUND
    assert result.stream_message.text_preview == "hello"
    assert chat_events.calls[0]["tenant_id"] == tenant_id


def test_ingest_reuses_existing_chat_event_for_duplicate_message() -> None:
    chat_events = FakeChatEventRepository()
    chat_events.created = False
    service = MessageIngestService(
        platform_service=FakePlatformService(uuid4()),
        chat_events=chat_events,
        settings=Settings(),
    )

    result = service.ingest_inbound_message(inbound_message())

    assert result.created is False
    assert result.chat_event_id == chat_events.chat_event_id


def test_ingest_fails_when_platform_mapping_is_missing() -> None:
    service = MessageIngestService(
        platform_service=FakePlatformService(None),
        chat_events=FakeChatEventRepository(),
        settings=Settings(),
    )

    with pytest.raises(ServiceError) as exc_info:
        service.ingest_inbound_message(inbound_message())

    assert exc_info.value.code == "TENANT_PLATFORM_NOT_FOUND"


def test_settings_reject_preview_limit_above_stream_contract() -> None:
    with pytest.raises(ValidationError):
        Settings(redis_text_preview_max_chars=501)
