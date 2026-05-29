from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from core.api.schemas.messages import (
    InboundMessageEnvelope,
    MessageDirection,
    OutboundMessageEnvelope,
    Platform,
    StreamMessageEnvelope,
)
from core.config import Settings
from core.streams.names import StreamDirection, stream_name


def test_inbound_message_envelope_rejects_tenant_id_spoofing() -> None:
    with pytest.raises(ValidationError):
        InboundMessageEnvelope.model_validate(
            {
                "trace_id": str(uuid4()),
                "tenant_id": str(uuid4()),
                "platform": "telegram",
                "external_workspace_id": "workspace-a",
                "channel_id": "channel-a",
                "user_id": "user-a",
                "message_id": "message-a",
                "text": "hello",
            }
        )


def test_inbound_message_envelope_requires_platform_message_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        InboundMessageEnvelope.model_validate({"trace_id": str(uuid4())})

    missing_fields = {error["loc"][0] for error in exc_info.value.errors()}
    assert {
        "platform",
        "external_workspace_id",
        "channel_id",
        "user_id",
        "message_id",
        "text",
    } <= missing_fields


def test_stream_message_envelope_contains_trusted_tenant_and_chat_event() -> None:
    tenant_id = uuid4()
    chat_event_id = uuid4()
    message = StreamMessageEnvelope(
        trace_id=uuid4(),
        tenant_id=tenant_id,
        chat_event_id=chat_event_id,
        direction=MessageDirection.INBOUND,
        platform=Platform.TELEGRAM,
        channel_id="channel-a",
        user_id="user-a",
        message_id="message-a",
        text_preview="hello",
    )

    dumped = message.model_dump(mode="json")
    assert dumped["tenant_id"] == str(tenant_id)
    assert dumped["chat_event_id"] == str(chat_event_id)
    assert dumped["platform"] == "telegram"
    assert dumped["direction"] == "inbound"


def test_outbound_message_envelope_preserves_trace_and_correlation() -> None:
    trace_id = uuid4()
    inbound_chat_event_id = uuid4()

    message = OutboundMessageEnvelope(
        trace_id=trace_id,
        tenant_id=uuid4(),
        platform=Platform.DISCORD,
        channel_id="channel-a",
        user_id="user-a",
        reply_to_message_id="message-a",
        inbound_chat_event_id=inbound_chat_event_id,
        text="stub response",
    )

    assert message.trace_id == trace_id
    assert message.inbound_chat_event_id == inbound_chat_event_id
    assert message.direction == MessageDirection.OUTBOUND


def test_stream_name_uses_environment_shared_direction_and_platform() -> None:
    assert (
        stream_name(
            environment="local",
            tenant_scope="shared",
            direction=StreamDirection.INGRESS,
            platform=Platform.TELEGRAM,
        )
        == "local:shared:ingress:telegram"
    )


def test_stream_name_rejects_empty_parts() -> None:
    with pytest.raises(ValueError, match="environment"):
        stream_name(
            environment="",
            tenant_scope="shared",
            direction=StreamDirection.OUTBOUND,
            platform=Platform.DISCORD,
        )


def test_redis_settings_defaults_are_explicit() -> None:
    settings = Settings()

    assert settings.redis_stream_max_length == 100_000
    assert settings.redis_publish_timeout_seconds == 1.0
    assert settings.redis_memory_warn_ratio == 0.80
    assert settings.redis_memory_reject_ratio == 0.90
    assert settings.redis_pending_reject_limit == 10_000
    assert settings.redis_pending_idle_reclaim_seconds == 300
    assert settings.redis_ingress_consumer_group == "message-stub"
    assert settings.redis_text_preview_max_chars == 500
    assert settings.redis_consumer_block_ms == 5_000
    assert settings.redis_consumer_batch_size == 10
    assert settings.redis_connection_pool_size == 10


def test_uuid_fields_accept_strings_and_dump_as_json_strings() -> None:
    trace_id = uuid4()
    message = InboundMessageEnvelope.model_validate(
        {
            "trace_id": str(trace_id),
            "platform": "telegram",
            "external_workspace_id": "workspace-a",
            "channel_id": "channel-a",
            "user_id": "user-a",
            "message_id": "message-a",
            "text": "hello",
        }
    )

    assert isinstance(message.trace_id, UUID)
    assert message.model_dump(mode="json")["trace_id"] == str(trace_id)
