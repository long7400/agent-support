from dataclasses import dataclass
from typing import Any

from redis.exceptions import ResponseError

from core.api.schemas.messages import StreamMessageEnvelope
from core.config import Settings, get_settings


@dataclass(frozen=True)
class StreamEntry:
    message_id: str
    payload: StreamMessageEnvelope


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
        response = self.redis.xreadgroup(
            groupname=group,
            consumername=consumer,
            streams={stream: ">"},
            count=self.settings.redis_consumer_batch_size,
            block=self.settings.redis_consumer_block_ms,
        )
        entries: list[StreamEntry] = []
        for _stream_name, messages in response:
            for message_id, fields in messages:
                entries.append(
                    StreamEntry(
                        message_id=_to_text(message_id),
                        payload=StreamMessageEnvelope.model_validate_json(
                            _to_text(_payload_field(fields))
                        ),
                    )
                )
        return entries

    def ack(self, *, stream: str, group: str, message_id: str) -> int:
        return int(self.redis.xack(stream, group, message_id))


def _to_text(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode()
    return str(value)


def _payload_field(fields: dict[Any, Any]) -> Any:
    if "payload" in fields:
        return fields["payload"]
    return fields[b"payload"]
