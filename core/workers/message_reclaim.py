from argparse import ArgumentParser
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from core.api.schemas.messages import OutboundMessageEnvelope, StreamMessageEnvelope
from core.config import Settings, get_settings
from core.services.errors import ServiceError
from core.streams.consumer import PendingEntrySummary, RedisStreamConsumer, StreamEntry
from core.streams.dlq import DlqMessageEnvelope, RedisDlqPublisher, dlq_envelope_from_entry
from core.streams.publisher import RedisStreamPublisher
from core.streams.redis_client import create_redis_client
from core.workers.message_stub import (
    TenantStatusVerifier,
    TenantStatusVerifierProtocol,
    _outbound_stub,
)


class StreamPublisherProtocol(Protocol):
    def publish(
        self,
        *,
        stream: str,
        envelope: StreamMessageEnvelope | OutboundMessageEnvelope,
        group: str | None = None,
    ) -> str: ...


class DlqPublisherProtocol(Protocol):
    def publish(self, *, stream: str, envelope: DlqMessageEnvelope) -> str: ...


@dataclass(frozen=True)
class ReclaimRunResult:
    processed: int
    moved_to_dlq: int
    reclaimed: int


class MessageReclaimWorker:
    def __init__(
        self,
        *,
        redis: object,
        settings: Settings | None = None,
        publisher: StreamPublisherProtocol | None = None,
        dlq_publisher: DlqPublisherProtocol | None = None,
        tenant_verifier: TenantStatusVerifierProtocol | None = None,
    ) -> None:
        self.redis = redis
        self.settings = settings or get_settings()
        self.consumer = RedisStreamConsumer(redis=redis, settings=self.settings)
        self.publisher = publisher or RedisStreamPublisher(redis=redis, settings=self.settings)
        self.dlq_publisher = dlq_publisher or RedisDlqPublisher(
            redis=redis,
            settings=self.settings,
        )
        self.tenant_verifier = tenant_verifier or TenantStatusVerifier()

    def run_once(
        self,
        *,
        ingress_stream: str,
        outbound_stream: str,
        dlq_stream: str,
        group: str,
        consumer: str,
    ) -> ReclaimRunResult:
        batch = self.consumer.reclaim_stale(
            stream=ingress_stream,
            group=group,
            consumer=consumer,
            min_idle_ms=self.settings.redis_reclaim_idle_millis,
            count=self.settings.redis_reclaim_batch_size,
        )
        processed = 0
        moved_to_dlq = 0
        first_error: ServiceError | None = None
        for entry in batch.entries:
            pending = self.consumer.pending_entry(
                stream=ingress_stream,
                group=group,
                message_id=entry.message_id,
            )
            delivery_count = pending.delivery_count if pending is not None else 1
            try:
                self.tenant_verifier.ensure_active(entry.payload.tenant_id)
                if delivery_count >= self.settings.redis_reclaim_retry_limit:
                    self._move_to_dlq(
                        ingress_stream=ingress_stream,
                        dlq_stream=dlq_stream,
                        entry=entry,
                        pending=pending,
                        retry_count=delivery_count,
                    )
                    self.consumer.ack(
                        stream=ingress_stream,
                        group=group,
                        message_id=entry.message_id,
                    )
                    moved_to_dlq += 1
                    continue
                self.publisher.publish(
                    stream=outbound_stream,
                    envelope=_outbound_stub(entry.payload),
                )
                self.consumer.ack(stream=ingress_stream, group=group, message_id=entry.message_id)
                processed += 1
            except ServiceError as exc:
                if first_error is None:
                    first_error = exc
        if first_error is not None:
            raise first_error
        return ReclaimRunResult(
            processed=processed,
            moved_to_dlq=moved_to_dlq,
            reclaimed=len(batch.entries),
        )

    def _move_to_dlq(
        self,
        *,
        ingress_stream: str,
        dlq_stream: str,
        entry: StreamEntry,
        pending: PendingEntrySummary | None,
        retry_count: int,
    ) -> None:
        consumer_name = pending.consumer if pending is not None else "unknown"
        envelope = dlq_envelope_from_entry(
            entry=entry,
            original_stream=ingress_stream,
            retry_count=retry_count,
            failure_class="RETRY_LIMIT_EXCEEDED",
            failure_summary=f"retry limit exceeded after reclaim by {consumer_name}",
        )
        self.dlq_publisher.publish(stream=dlq_stream, envelope=envelope)


def run(argv: Sequence[str] | None = None) -> None:
    parser = ArgumentParser(description="Run one deterministic Redis reclaim/DLQ batch")
    parser.add_argument("--ingress-stream", required=True)
    parser.add_argument("--outbound-stream", required=True)
    parser.add_argument("--dlq-stream", required=True)
    parser.add_argument("--group", default=None)
    parser.add_argument("--consumer", default="reclaim-1")
    args = parser.parse_args(argv)
    settings = get_settings()
    redis = create_redis_client(settings)
    result = MessageReclaimWorker(redis=redis, settings=settings).run_once(
        ingress_stream=args.ingress_stream,
        outbound_stream=args.outbound_stream,
        dlq_stream=args.dlq_stream,
        group=args.group or settings.redis_ingress_consumer_group,
        consumer=args.consumer,
    )
    print(
        "processed="
        f"{result.processed} moved_to_dlq={result.moved_to_dlq} reclaimed={result.reclaimed}"
    )
