import json
import logging
from time import perf_counter
from typing import Any

from redis.exceptions import RedisError

from core.api.schemas.messages import OutboundMessageEnvelope, StreamMessageEnvelope
from core.config import Settings, get_settings
from core.services.errors import ServiceError
from core.streams.backpressure import RedisBackpressureChecker

logger = logging.getLogger(__name__)

RedisStreamPayload = StreamMessageEnvelope | OutboundMessageEnvelope


class RedisStreamPublisher:
    def __init__(
        self,
        *,
        redis: Any,
        settings: Settings | None = None,
        backpressure: RedisBackpressureChecker | None = None,
    ) -> None:
        self.redis = redis
        self.settings = settings or get_settings()
        self.backpressure = backpressure or RedisBackpressureChecker(
            redis=redis,
            settings=self.settings,
        )

    def publish(
        self,
        *,
        stream: str,
        envelope: RedisStreamPayload,
        group: str | None = None,
    ) -> str:
        self.backpressure.ensure_can_publish(stream=stream, group=group)
        payload = json.dumps(
            envelope.model_dump(mode="json"),
            separators=(",", ":"),
            sort_keys=True,
        )
        started = perf_counter()
        try:
            message_id = self.redis.xadd(
                stream,
                {"payload": payload},
                maxlen=self.settings.redis_stream_max_length,
                approximate=True,
            )
        except RedisError as exc:
            logger.warning(
                "redis_stream_publish_failed",
                extra={
                    "stream": stream,
                    "tenant_id": str(envelope.tenant_id),
                    "trace_id": str(envelope.trace_id),
                    "error_class": type(exc).__name__,
                    "latency_ms": round((perf_counter() - started) * 1000, 3),
                },
            )
            raise ServiceError(
                code="QUEUE_BACKPRESSURE",
                message="Redis stream publish failed",
                status_code=503,
            ) from exc
        logger.info(
            "redis_stream_publish_succeeded",
            extra={
                "stream": stream,
                "tenant_id": str(envelope.tenant_id),
                "trace_id": str(envelope.trace_id),
                "latency_ms": round((perf_counter() - started) * 1000, 3),
            },
        )
        if isinstance(message_id, bytes):
            return message_id.decode()
        return str(message_id)
