import logging
from dataclasses import dataclass
from typing import Any

from redis.exceptions import RedisError, ResponseError

from core.config import Settings, get_settings
from core.services.errors import ServiceError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BackpressureState:
    used_memory: int
    maxmemory: int
    memory_ratio: float
    memory_warning: bool
    memory_rejected: bool
    stream_length: int
    pending_count: int


class RedisBackpressureChecker:
    def __init__(self, *, redis: Any, settings: Settings | None = None) -> None:
        self.redis = redis
        self.settings = settings or get_settings()

    def ensure_can_publish(self, *, stream: str, group: str | None) -> BackpressureState:
        try:
            state = self.inspect(stream=stream, group=group)
        except RedisError as exc:
            logger.warning(
                "redis_backpressure_probe_failed",
                extra={"stream": stream, "group": group, "error_class": type(exc).__name__},
            )
            raise _queue_backpressure("Redis backpressure probe failed") from exc
        if state.memory_rejected:
            raise _queue_backpressure("Redis memory usage is above the reject threshold")
        if state.stream_length >= self.settings.redis_stream_max_length:
            raise _queue_backpressure("Redis stream length is above the configured limit")
        if state.pending_count >= self.settings.redis_pending_reject_limit:
            raise _queue_backpressure("Redis pending entries are above the configured limit")
        return state

    def inspect(self, *, stream: str, group: str | None) -> BackpressureState:
        memory_info = self.redis.info("memory")
        used_memory = int(memory_info.get("used_memory", 0))
        maxmemory = int(memory_info.get("maxmemory", 0))
        memory_ratio = used_memory / maxmemory if maxmemory > 0 else 0.0
        stream_length = int(self.redis.xlen(stream))
        pending_count = self._pending_count(stream=stream, group=group)
        return BackpressureState(
            used_memory=used_memory,
            maxmemory=maxmemory,
            memory_ratio=memory_ratio,
            memory_warning=memory_ratio >= self.settings.redis_memory_warn_ratio,
            memory_rejected=memory_ratio >= self.settings.redis_memory_reject_ratio,
            stream_length=stream_length,
            pending_count=pending_count,
        )

    def _pending_count(self, *, stream: str, group: str | None) -> int:
        if group is None:
            return 0
        try:
            pending = self.redis.xpending(stream, group)
        except ResponseError as exc:
            if "NOGROUP" in str(exc):
                return 0
            raise
        if isinstance(pending, dict):
            return int(pending.get("pending", 0))
        return 0


def _queue_backpressure(message: str) -> ServiceError:
    return ServiceError(code="QUEUE_BACKPRESSURE", message=message, status_code=503)
