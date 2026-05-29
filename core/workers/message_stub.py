from argparse import ArgumentParser
from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from core.api.schemas.messages import OutboundMessageEnvelope, StreamMessageEnvelope
from core.config import Settings, get_settings
from core.constants import STREAM_TEXT_PREVIEW_MAX_CHARS
from core.persistence.db import create_session_factory
from core.persistence.repositories.tenants import TenantRepository
from core.persistence.rls import tenant_session
from core.services.errors import ServiceError
from core.streams.consumer import RedisStreamConsumer
from core.streams.publisher import RedisStreamPublisher
from core.streams.redis_client import create_redis_client


class StreamPublisherProtocol(Protocol):
    def publish(
        self,
        *,
        stream: str,
        envelope: StreamMessageEnvelope | OutboundMessageEnvelope,
        group: str | None = None,
    ) -> str: ...


class TenantStatusVerifierProtocol(Protocol):
    def ensure_active(self, tenant_id: UUID) -> None: ...


class TenantStatusVerifier:
    def __init__(self, session_factory: sessionmaker[Session] | None = None) -> None:
        self.session_factory = session_factory or create_session_factory()

    def ensure_active(self, tenant_id: UUID) -> None:
        with tenant_session(tenant_id, self.session_factory) as session:
            tenant = TenantRepository(session).get(tenant_id)
            if tenant is None:
                raise ServiceError(
                    code="TENANT_NOT_FOUND",
                    message="Tenant not found",
                    status_code=404,
                )
            if tenant.status != "active":
                raise ServiceError(
                    code="TENANT_INACTIVE",
                    message="Tenant is not active",
                    status_code=409,
                )


class MessageStubWorker:
    def __init__(
        self,
        *,
        redis: object,
        settings: Settings | None = None,
        publisher: StreamPublisherProtocol | None = None,
        tenant_verifier: TenantStatusVerifierProtocol | None = None,
    ) -> None:
        self.redis = redis
        self.settings = settings or get_settings()
        self.consumer = RedisStreamConsumer(redis=redis, settings=self.settings)
        self.publisher = publisher or RedisStreamPublisher(redis=redis, settings=self.settings)
        self.tenant_verifier = tenant_verifier or TenantStatusVerifier()

    def run_once(
        self,
        *,
        ingress_stream: str,
        outbound_stream: str,
        group: str,
        consumer: str,
    ) -> int:
        self.consumer.create_group(stream=ingress_stream, group=group)
        entries = self.consumer.read_group(stream=ingress_stream, group=group, consumer=consumer)
        processed = 0
        first_error: ServiceError | None = None
        for entry in entries:
            try:
                self.tenant_verifier.ensure_active(entry.payload.tenant_id)
                outbound = _outbound_stub(entry.payload)
                self.publisher.publish(stream=outbound_stream, envelope=outbound)
                self.consumer.ack(stream=ingress_stream, group=group, message_id=entry.message_id)
                processed += 1
            except ServiceError as exc:
                if first_error is None:
                    first_error = exc
        if first_error is not None:
            raise first_error
        return processed


def _outbound_stub(inbound: StreamMessageEnvelope) -> OutboundMessageEnvelope:
    return OutboundMessageEnvelope(
        trace_id=inbound.trace_id,
        tenant_id=inbound.tenant_id,
        platform=inbound.platform,
        channel_id=inbound.channel_id,
        user_id=inbound.user_id,
        reply_to_message_id=inbound.message_id,
        inbound_chat_event_id=inbound.chat_event_id,
        text=f"stub:{inbound.text_preview}"[:STREAM_TEXT_PREVIEW_MAX_CHARS],
    )


def run(argv: Sequence[str] | None = None) -> None:
    parser = ArgumentParser(description="Run one deterministic message worker stub batch")
    parser.add_argument("--ingress-stream", required=True)
    parser.add_argument("--outbound-stream", required=True)
    parser.add_argument("--group", default=None)
    parser.add_argument("--consumer", default="worker-1")
    args = parser.parse_args(argv)
    settings = get_settings()
    redis = create_redis_client(settings)
    processed = MessageStubWorker(redis=redis, settings=settings).run_once(
        ingress_stream=args.ingress_stream,
        outbound_stream=args.outbound_stream,
        group=args.group or settings.redis_ingress_consumer_group,
        consumer=args.consumer,
    )
    print(f"processed={processed}")
