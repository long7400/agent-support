from dataclasses import dataclass
from typing import Any

from redis.exceptions import RedisError, ResponseError

from core.api.schemas.messages import OutboundMessageEnvelope, StreamMessageEnvelope
from core.config import Settings, get_settings
from core.services.errors import ServiceError


@dataclass(frozen=True)
class StreamEntry:
    message_id: str
    payload: StreamMessageEnvelope


@dataclass(frozen=True)
class OutboundStreamEntry:
    message_id: str
    payload: OutboundMessageEnvelope


@dataclass(frozen=True)
class PendingEntrySummary:
    message_id: str
    consumer: str
    idle_ms: int
    delivery_count: int


@dataclass(frozen=True)
class ReclaimedBatch:
    next_start_id: str
    entries: list[StreamEntry]
    deleted_ids: list[str]


class RedisStreamConsumer:
    def __init__(self, *, redis: Any, settings: Settings | None = None) -> None:
        self.redis = redis
        self.settings = settings or get_settings()

    def create_group(self, *, stream: str, group: str, start_id: str = "0") -> None:
        try:
            self.redis.xgroup_create(
                name=stream,
                groupname=group,
                id=start_id,
                mkstream=True,
            )
        except ResponseError as exc:
            if "BUSYGROUP" in str(exc):
                return
            raise

    def read_group(self, *, stream: str, group: str, consumer: str) -> list[StreamEntry]:
        try:
            response = self.redis.xreadgroup(
                groupname=group,
                consumername=consumer,
                streams={stream: ">"},
                count=self.settings.redis_consumer_batch_size,
                block=self.settings.redis_consumer_block_ms,
            )
        except RedisError as exc:
            raise ServiceError(
                code="STREAM_CONSUME_FAILED",
                message="Redis stream read failed",
                status_code=503,
            ) from exc
        return [
            StreamEntry(
                message_id=message_id,
                payload=StreamMessageEnvelope.model_validate_json(payload),
            )
            for message_id, payload in _stream_payloads(response)
        ]

    def read_outbound_group(
        self,
        *,
        stream: str,
        group: str,
        consumer: str,
    ) -> list[OutboundStreamEntry]:
        try:
            response = self.redis.xreadgroup(
                groupname=group,
                consumername=consumer,
                streams={stream: ">"},
                count=self.settings.redis_consumer_batch_size,
                block=self.settings.redis_consumer_block_ms,
            )
        except RedisError as exc:
            raise ServiceError(
                code="STREAM_CONSUME_FAILED",
                message="Redis outbound stream read failed",
                status_code=503,
            ) from exc
        return [
            OutboundStreamEntry(
                message_id=message_id,
                payload=OutboundMessageEnvelope.model_validate_json(payload),
            )
            for message_id, payload in _stream_payloads(response)
        ]

    def ack(self, *, stream: str, group: str, message_id: str) -> int:
        try:
            return int(self.redis.xack(stream, group, message_id))
        except RedisError as exc:
            raise ServiceError(
                code="STREAM_ACK_FAILED",
                message="Redis stream ACK failed",
                status_code=503,
            ) from exc

    def pending_entries(self, *, stream: str, group: str, count: int) -> list[PendingEntrySummary]:
        try:
            response = self.redis.xpending_range(stream, group, "-", "+", count)
        except RedisError as exc:
            raise ServiceError(
                code="STREAM_CONSUME_FAILED",
                message="Redis pending inspection failed",
                status_code=503,
            ) from exc
        return [_pending_entry(item) for item in response]

    def pending_entry(
        self,
        *,
        stream: str,
        group: str,
        message_id: str,
    ) -> PendingEntrySummary | None:
        try:
            response = self.redis.xpending_range(stream, group, message_id, message_id, 1)
        except RedisError as exc:
            raise ServiceError(
                code="STREAM_CONSUME_FAILED",
                message="Redis pending inspection failed",
                status_code=503,
            ) from exc
        entries = [_pending_entry(item) for item in response]
        return entries[0] if entries else None

    def reclaim_stale(
        self,
        *,
        stream: str,
        group: str,
        consumer: str,
        min_idle_ms: int,
        start_id: str = "0-0",
        count: int | None = None,
    ) -> ReclaimedBatch:
        try:
            response = self.redis.xautoclaim(
                stream,
                group,
                consumer,
                min_idle_ms,
                start_id,
                count=count or self.settings.redis_reclaim_batch_size,
            )
        except RedisError as exc:
            raise ServiceError(
                code="STREAM_CONSUME_FAILED",
                message="Redis pending reclaim failed",
                status_code=503,
            ) from exc
        next_start_id, messages, deleted = _autoclaim_parts(response)
        return ReclaimedBatch(
            next_start_id=next_start_id,
            entries=[
                StreamEntry(
                    message_id=_to_text(message_id),
                    payload=StreamMessageEnvelope.model_validate_json(
                        _to_text(_payload_field(fields))
                    ),
                )
                for message_id, fields in messages
            ],
            deleted_ids=[_to_text(message_id) for message_id in deleted],
        )


def _to_text(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode()
    return str(value)


def _payload_field(fields: dict[Any, Any]) -> Any:
    if "payload" in fields:
        return fields["payload"]
    return fields[b"payload"]


def _stream_payloads(
    response: list[tuple[Any, list[tuple[Any, dict[Any, Any]]]]],
) -> list[tuple[str, str]]:
    payloads: list[tuple[str, str]] = []
    for _stream_name, messages in response:
        for message_id, fields in messages:
            payloads.append((_to_text(message_id), _to_text(_payload_field(fields))))
    return payloads


def _pending_entry(item: Any) -> PendingEntrySummary:
    if isinstance(item, dict):
        return PendingEntrySummary(
            message_id=_to_text(item["message_id"]),
            consumer=_to_text(item["consumer"]),
            idle_ms=int(item["time_since_delivered"]),
            delivery_count=int(item["times_delivered"]),
        )
    return PendingEntrySummary(
        message_id=_to_text(item[0]),
        consumer=_to_text(item[1]),
        idle_ms=int(item[2]),
        delivery_count=int(item[3]),
    )


def _autoclaim_parts(response: Any) -> tuple[str, list[tuple[Any, dict[Any, Any]]], list[Any]]:
    next_start_id = _to_text(response[0])
    messages = list(response[1])
    deleted = list(response[2]) if len(response) > 2 else []
    return next_start_id, messages, deleted
