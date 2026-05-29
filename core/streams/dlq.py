import json
import logging
from time import perf_counter
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from redis.exceptions import RedisError

from core.api.schemas.messages import Platform, StreamMessageEnvelope
from core.config import Settings, get_settings
from core.services.errors import ServiceError
from core.services.redaction import redact_sensitive_value
from core.streams.consumer import StreamEntry

logger = logging.getLogger(__name__)

DLQ_FAILURE_SUMMARY_MAX_CHARS = 300


class DlqMessageEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trace_id: UUID
    tenant_id: UUID
    platform: Platform
    original_stream: str = Field(min_length=1)
    original_stream_id: str = Field(min_length=1)
    retry_count: int = Field(ge=0)
    failure_class: str = Field(min_length=1, max_length=128)
    failure_summary: str = Field(max_length=DLQ_FAILURE_SUMMARY_MAX_CHARS)


class RedisDlqPublisher:
    def __init__(self, *, redis: Any, settings: Settings | None = None) -> None:
        self.redis = redis
        self.settings = settings or get_settings()

    def publish(self, *, stream: str, envelope: DlqMessageEnvelope) -> str:
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
                maxlen=self.settings.redis_dlq_max_length,
                approximate=True,
            )
        except RedisError as exc:
            logger.warning(
                "redis_dlq_publish_failed",
                extra={
                    "stream": stream,
                    "tenant_id": str(envelope.tenant_id),
                    "trace_id": str(envelope.trace_id),
                    "platform": envelope.platform.value,
                    "error_class": type(exc).__name__,
                    "latency_ms": round((perf_counter() - started) * 1000, 3),
                },
            )
            raise ServiceError(
                code="DLQ_PUBLISH_FAILED",
                message="Redis DLQ publish failed",
                status_code=503,
            ) from exc
        logger.info(
            "redis_dlq_publish_succeeded",
            extra={
                "stream": stream,
                "tenant_id": str(envelope.tenant_id),
                "trace_id": str(envelope.trace_id),
                "platform": envelope.platform.value,
                "latency_ms": round((perf_counter() - started) * 1000, 3),
            },
        )
        if isinstance(message_id, bytes):
            return message_id.decode()
        return str(message_id)


def dlq_envelope_from_entry(
    *,
    entry: StreamEntry,
    original_stream: str,
    retry_count: int,
    failure_class: str,
    failure_summary: str,
) -> DlqMessageEnvelope:
    payload: StreamMessageEnvelope = entry.payload
    return DlqMessageEnvelope(
        trace_id=payload.trace_id,
        tenant_id=payload.tenant_id,
        platform=payload.platform,
        original_stream=original_stream,
        original_stream_id=entry.message_id,
        retry_count=retry_count,
        failure_class=failure_class,
        failure_summary=redacted_failure_summary(failure_summary),
    )


def redacted_failure_summary(value: str) -> str:
    redacted = redact_sensitive_value(value)
    summary = redacted if isinstance(redacted, str) else str(redacted)
    return summary[:DLQ_FAILURE_SUMMARY_MAX_CHARS]


def retry_limit_exceeded(*, delivery_count: int, retry_limit: int) -> bool:
    return delivery_count >= retry_limit
