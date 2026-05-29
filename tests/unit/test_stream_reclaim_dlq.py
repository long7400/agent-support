import json
from uuid import uuid4

import pytest
from redis.exceptions import TimeoutError

from core.api.schemas.messages import MessageDirection, Platform, StreamMessageEnvelope
from core.config import Settings
from core.services.errors import ServiceError
from core.streams.consumer import RedisStreamConsumer, StreamEntry
from core.streams.dlq import (
    DlqMessageEnvelope,
    RedisDlqPublisher,
    dlq_envelope_from_entry,
    redacted_failure_summary,
    retry_limit_exceeded,
)
from core.workers.message_reclaim import MessageReclaimWorker


class FakeRedis:
    def __init__(self) -> None:
        self.acked: list[tuple[str, str, str]] = []
        self.xadd_calls: list[dict[str, object]] = []
        self.autoclaimed = False

    def xpending_range(
        self,
        stream: str,
        group: str,
        start: str,
        end: str,
        count: int,
    ) -> list[dict[str, object]]:
        del stream, group, start, end, count
        delivery_count = 3 if self.autoclaimed else 2
        return [
            {
                "message_id": b"1-0",
                "consumer": b"worker-a",
                "time_since_delivered": 1234,
                "times_delivered": delivery_count,
            }
        ]

    def xautoclaim(
        self,
        stream: str,
        group: str,
        consumer: str,
        min_idle_time: int,
        start_id: str,
        *,
        count: int,
    ) -> tuple[str, list[tuple[str, dict[str, str]]], list[str]]:
        del stream, group, consumer, min_idle_time, start_id, count
        self.autoclaimed = True
        payload = stream_envelope().model_dump_json()
        return ("0-0", [("1-0", {"payload": payload})], [])

    def xack(self, stream: str, group: str, message_id: str) -> int:
        self.acked.append((stream, group, message_id))
        return 1

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
        return "2-0"


class FailingPendingRedis(FakeRedis):
    def xpending_range(
        self,
        stream: str,
        group: str,
        start: str,
        end: str,
        count: int,
    ) -> list[dict[str, object]]:
        del stream, group, start, end, count
        raise TimeoutError("timed out")


class FailingAckRedis(FakeRedis):
    def xack(self, stream: str, group: str, message_id: str) -> int:
        del stream, group, message_id
        raise TimeoutError("timed out")


class FakeTenantVerifier:
    def ensure_active(self, tenant_id: object) -> None:
        del tenant_id


class FakeStreamPublisher:
    def __init__(self) -> None:
        self.published = 0

    def publish(self, *, stream: str, envelope: object, group: str | None = None) -> str:
        del stream, envelope, group
        self.published += 1
        return "2-0"


def stream_envelope() -> StreamMessageEnvelope:
    return StreamMessageEnvelope(
        trace_id=uuid4(),
        tenant_id=uuid4(),
        chat_event_id=uuid4(),
        direction=MessageDirection.INBOUND,
        platform=Platform.TELEGRAM,
        channel_id="channel-a",
        user_id="user-a",
        message_id="message-a",
        text_preview="hello private text",
    )


def test_pending_entries_parse_redis_response() -> None:
    consumer = RedisStreamConsumer(redis=FakeRedis(), settings=Settings())

    entries = consumer.pending_entries(stream="ingress", group="workers", count=10)

    assert entries[0].message_id == "1-0"
    assert entries[0].consumer == "worker-a"
    assert entries[0].idle_ms == 1234
    assert entries[0].delivery_count == 2


def test_pending_entry_reads_updated_delivery_count_after_reclaim() -> None:
    redis = FakeRedis()
    consumer = RedisStreamConsumer(redis=redis, settings=Settings())

    consumer.reclaim_stale(
        stream="ingress",
        group="workers",
        consumer="reclaimer",
        min_idle_ms=0,
    )
    entry = consumer.pending_entry(stream="ingress", group="workers", message_id="1-0")

    assert entry is not None
    assert entry.delivery_count == 3


def test_reclaim_stale_parses_autoclaim_payload() -> None:
    consumer = RedisStreamConsumer(redis=FakeRedis(), settings=Settings())

    batch = consumer.reclaim_stale(
        stream="ingress",
        group="workers",
        consumer="reclaimer",
        min_idle_ms=0,
    )

    assert batch.next_start_id == "0-0"
    assert batch.deleted_ids == []
    assert batch.entries[0].message_id == "1-0"
    assert batch.entries[0].payload.platform == Platform.TELEGRAM


def test_pending_probe_failures_are_typed_service_errors() -> None:
    consumer = RedisStreamConsumer(redis=FailingPendingRedis(), settings=Settings())

    with pytest.raises(ServiceError) as exc_info:
        consumer.pending_entries(stream="ingress", group="workers", count=10)

    assert exc_info.value.code == "STREAM_CONSUME_FAILED"


def test_ack_failures_are_typed_service_errors() -> None:
    consumer = RedisStreamConsumer(redis=FailingAckRedis(), settings=Settings())

    with pytest.raises(ServiceError) as exc_info:
        consumer.ack(stream="ingress", group="workers", message_id="1-0")

    assert exc_info.value.code == "STREAM_ACK_FAILED"


def test_retry_limit_classification_is_explicit() -> None:
    assert retry_limit_exceeded(delivery_count=3, retry_limit=3) is True
    assert retry_limit_exceeded(delivery_count=2, retry_limit=3) is False


def test_reclaim_worker_uses_post_claim_delivery_count_for_dlq() -> None:
    redis = FakeRedis()
    publisher = FakeStreamPublisher()
    worker = MessageReclaimWorker(
        redis=redis,
        settings=Settings(redis_reclaim_retry_limit=3),
        publisher=publisher,
        tenant_verifier=FakeTenantVerifier(),
    )

    result = worker.run_once(
        ingress_stream="ingress",
        outbound_stream="outbound",
        dlq_stream="dlq",
        group="workers",
        consumer="reclaimer",
    )

    assert result.moved_to_dlq == 1
    assert result.processed == 0
    assert publisher.published == 0
    assert redis.acked == [("ingress", "workers", "1-0")]
    assert redis.xadd_calls[0]["name"] == "dlq"


def test_dlq_payload_preserves_context_without_message_text() -> None:
    envelope = stream_envelope()
    dlq = dlq_envelope_from_entry(
        entry=StreamEntry(message_id="1-0", payload=envelope),
        original_stream="local:tenant:ingress:telegram",
        retry_count=3,
        failure_class="RETRY_LIMIT_EXCEEDED",
        failure_summary="retry limit exceeded",
    )

    dumped = dlq.model_dump(mode="json")
    assert dumped["trace_id"] == str(envelope.trace_id)
    assert dumped["tenant_id"] == str(envelope.tenant_id)
    assert dumped["platform"] == "telegram"
    assert dumped["original_stream_id"] == "1-0"
    assert dumped["retry_count"] == 3
    assert "hello private text" not in dlq.model_dump_json()


def test_dlq_redacts_secret_like_failure_summary() -> None:
    assert redacted_failure_summary("token=super-secret-value") == "[REDACTED]"


def test_dlq_publisher_uses_bounded_stream_payload() -> None:
    redis = FakeRedis()
    publisher = RedisDlqPublisher(redis=redis, settings=Settings(redis_dlq_max_length=25))
    envelope = DlqMessageEnvelope(
        trace_id=uuid4(),
        tenant_id=uuid4(),
        platform=Platform.TELEGRAM,
        original_stream="local:tenant:ingress:telegram",
        original_stream_id="1-0",
        retry_count=3,
        failure_class="RETRY_LIMIT_EXCEEDED",
        failure_summary="retry limit exceeded",
    )

    message_id = publisher.publish(stream="local:tenant:dlq:telegram", envelope=envelope)
    payload = json.loads(redis.xadd_calls[0]["fields"]["payload"])  # type: ignore[index]

    assert message_id == "2-0"
    assert redis.xadd_calls[0]["maxlen"] == 25
    assert redis.xadd_calls[0]["approximate"] is True
    assert payload["original_stream_id"] == "1-0"
