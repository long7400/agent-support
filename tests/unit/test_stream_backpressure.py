from uuid import uuid4

import pytest
from redis.exceptions import ResponseError, TimeoutError

from core.api.schemas.messages import MessageDirection, Platform, StreamMessageEnvelope
from core.config import Settings
from core.services.errors import ServiceError
from core.streams.backpressure import RedisBackpressureChecker
from core.streams.publisher import RedisStreamPublisher


class FakeRedis:
    def __init__(
        self,
        *,
        used_memory: int = 10,
        maxmemory: int = 100,
        stream_length: int = 0,
        pending_count: int = 0,
    ) -> None:
        self.used_memory = used_memory
        self.maxmemory = maxmemory
        self.stream_length = stream_length
        self.pending_count = pending_count
        self.xadd_calls: list[dict[str, object]] = []

    def info(self, section: str) -> dict[str, int]:
        assert section == "memory"
        return {"used_memory": self.used_memory, "maxmemory": self.maxmemory}

    def xlen(self, stream: str) -> int:
        del stream
        return self.stream_length

    def xpending(self, stream: str, group: str) -> dict[str, int]:
        del stream, group
        return {"pending": self.pending_count}

    def xadd(
        self,
        name: str,
        fields: dict[str, str],
        *,
        maxlen: int,
        approximate: bool,
    ) -> str:
        self.xadd_calls.append(
            {
                "name": name,
                "fields": fields,
                "maxlen": maxlen,
                "approximate": approximate,
            }
        )
        return "1-0"


class FailingInfoRedis(FakeRedis):
    def info(self, section: str) -> dict[str, int]:
        del section
        raise TimeoutError("timed out")


class FailingXaddRedis(FakeRedis):
    def xadd(
        self,
        name: str,
        fields: dict[str, str],
        *,
        maxlen: int,
        approximate: bool,
    ) -> str:
        del name, fields, maxlen, approximate
        raise ResponseError("OOM command not allowed when used memory > 'maxmemory'.")


def test_backpressure_warns_without_rejecting_below_reject_threshold() -> None:
    checker = RedisBackpressureChecker(
        redis=FakeRedis(used_memory=80, maxmemory=100),
        settings=Settings(redis_memory_warn_ratio=0.50, redis_memory_reject_ratio=0.90),
    )

    state = checker.ensure_can_publish(stream="ingress", group=None)

    assert state.memory_warning is True
    assert state.memory_rejected is False


def test_backpressure_rejects_when_memory_ratio_reaches_reject_threshold() -> None:
    checker = RedisBackpressureChecker(
        redis=FakeRedis(used_memory=95, maxmemory=100),
        settings=Settings(redis_memory_warn_ratio=0.50, redis_memory_reject_ratio=0.90),
    )

    with pytest.raises(ServiceError) as exc_info:
        checker.ensure_can_publish(stream="ingress", group=None)

    assert exc_info.value.code == "QUEUE_BACKPRESSURE"


def test_backpressure_rejects_when_stream_length_reaches_limit() -> None:
    checker = RedisBackpressureChecker(
        redis=FakeRedis(stream_length=5),
        settings=Settings(redis_stream_max_length=5),
    )

    with pytest.raises(ServiceError) as exc_info:
        checker.ensure_can_publish(stream="ingress", group=None)

    assert exc_info.value.code == "QUEUE_BACKPRESSURE"


def test_backpressure_rejects_when_pending_count_reaches_limit() -> None:
    checker = RedisBackpressureChecker(
        redis=FakeRedis(pending_count=3),
        settings=Settings(redis_pending_reject_limit=3),
    )

    with pytest.raises(ServiceError) as exc_info:
        checker.ensure_can_publish(stream="ingress", group="workers")

    assert exc_info.value.code == "QUEUE_BACKPRESSURE"


def test_backpressure_probe_failures_return_typed_queue_error() -> None:
    checker = RedisBackpressureChecker(redis=FailingInfoRedis(), settings=Settings())

    with pytest.raises(ServiceError) as exc_info:
        checker.ensure_can_publish(stream="ingress", group=None)

    assert exc_info.value.code == "QUEUE_BACKPRESSURE"


def test_publisher_uses_bounded_xadd_and_json_payload() -> None:
    redis = FakeRedis()
    publisher = RedisStreamPublisher(
        redis=redis,
        settings=Settings(redis_stream_max_length=25),
    )
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

    message_id = publisher.publish(stream="ingress", envelope=envelope)

    assert message_id == "1-0"
    assert redis.xadd_calls[0]["maxlen"] == 25
    assert redis.xadd_calls[0]["approximate"] is True
    assert '"tenant_id":' in redis.xadd_calls[0]["fields"]["payload"]  # type: ignore[index]


def test_publisher_maps_redis_response_errors_to_queue_backpressure() -> None:
    publisher = RedisStreamPublisher(redis=FailingXaddRedis(), settings=Settings())
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

    with pytest.raises(ServiceError) as exc_info:
        publisher.publish(stream="ingress", envelope=envelope)

    assert exc_info.value.code == "QUEUE_BACKPRESSURE"
