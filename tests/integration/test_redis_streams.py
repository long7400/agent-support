import os
from uuid import uuid4

import pytest

from core.api.schemas.messages import MessageDirection, Platform, StreamMessageEnvelope
from core.config import Settings, get_settings
from core.services.errors import ServiceError
from core.streams.consumer import RedisStreamConsumer
from core.streams.publisher import RedisStreamPublisher
from core.streams.redis_client import create_redis_client

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def require_integration() -> None:
    if os.getenv("AGENT_SUPPORT_RUN_INTEGRATION") != "1":
        pytest.skip("set AGENT_SUPPORT_RUN_INTEGRATION=1 to run integration tests")


def test_redis_stream_publish_read_pending_and_ack(require_integration: None) -> None:
    del require_integration
    settings = Settings(redis_url=get_settings().redis_url, redis_consumer_block_ms=100)
    redis = create_redis_client(settings)
    stream = f"test:ingress:{uuid4()}"
    group = f"workers:{uuid4()}"
    consumer_name = "worker-a"
    envelope = StreamMessageEnvelope(
        trace_id=uuid4(),
        tenant_id=uuid4(),
        chat_event_id=uuid4(),
        direction=MessageDirection.INBOUND,
        platform=Platform.TELEGRAM,
        channel_id="channel-a",
        user_id="user-a",
        message_id="message-a",
        text_preview="hello",
    )
    stream_consumer = RedisStreamConsumer(redis=redis, settings=settings)

    try:
        stream_consumer.create_group(stream=stream, group=group)
        message_id = RedisStreamPublisher(redis=redis, settings=settings).publish(
            stream=stream,
            envelope=envelope,
        )

        entries = stream_consumer.read_group(
            stream=stream,
            group=group,
            consumer=consumer_name,
        )
        pending_before_ack = redis.xpending(stream, group)["pending"]
        acked = stream_consumer.ack(stream=stream, group=group, message_id=message_id)
        pending_after_ack = redis.xpending(stream, group)["pending"]

    finally:
        redis.delete(stream)

    assert len(entries) == 1
    assert entries[0].message_id == message_id
    assert entries[0].payload.chat_event_id == envelope.chat_event_id
    assert pending_before_ack == 1
    assert acked == 1
    assert pending_after_ack == 0


def test_redis_stream_publisher_rejects_when_stream_length_limit_is_reached(
    require_integration: None,
) -> None:
    del require_integration
    settings = Settings(redis_url=get_settings().redis_url, redis_stream_max_length=1)
    redis = create_redis_client(settings)
    stream = f"test:ingress:{uuid4()}"
    envelope = StreamMessageEnvelope(
        trace_id=uuid4(),
        tenant_id=uuid4(),
        chat_event_id=uuid4(),
        direction=MessageDirection.INBOUND,
        platform=Platform.TELEGRAM,
        channel_id="channel-a",
        user_id="user-a",
        message_id="message-a",
        text_preview="hello",
    )
    publisher = RedisStreamPublisher(redis=redis, settings=settings)
    length_after_reject = -1

    try:
        publisher.publish(stream=stream, envelope=envelope)

        with pytest.raises(ServiceError) as exc_info:
            publisher.publish(stream=stream, envelope=envelope)
        length_after_reject = redis.xlen(stream)

    finally:
        redis.delete(stream)

    assert exc_info.value.code == "QUEUE_BACKPRESSURE"
    assert length_after_reject == 1
