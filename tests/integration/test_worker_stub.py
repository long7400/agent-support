import os
from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from core.api.schemas.messages import MessageDirection, Platform, StreamMessageEnvelope
from core.config import Settings, get_settings
from core.services.errors import ServiceError
from core.streams.consumer import RedisStreamConsumer
from core.streams.publisher import RedisStreamPublisher
from core.streams.redis_client import create_redis_client
from core.workers.message_stub import MessageStubWorker

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def require_integration() -> None:
    if os.getenv("AGENT_SUPPORT_RUN_INTEGRATION") != "1":
        pytest.skip("set AGENT_SUPPORT_RUN_INTEGRATION=1 to run integration tests")


@pytest.fixture()
def admin_session_factory(require_integration: None) -> Iterator[sessionmaker[Session]]:
    del require_integration
    engine = create_engine(get_settings().database_admin_url, pool_pre_ping=True)
    try:
        yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    finally:
        engine.dispose()


def create_tenant(admin_session_factory: sessionmaker[Session], *, status: str = "active") -> UUID:
    tenant_id = uuid4()
    with admin_session_factory() as session, session.begin():
        session.execute(
            text("INSERT INTO tenants (id, slug, status) VALUES (:id, :slug, :status)"),
            {
                "id": tenant_id,
                "slug": f"tenant-worker-stub-{tenant_id}",
                "status": status,
            },
        )
    return tenant_id


def stream_envelope(
    *,
    tenant_id: UUID | None = None,
    message_id: str = "message-a",
) -> StreamMessageEnvelope:
    return StreamMessageEnvelope(
        trace_id=uuid4(),
        tenant_id=tenant_id or uuid4(),
        chat_event_id=uuid4(),
        direction=MessageDirection.INBOUND,
        platform=Platform.TELEGRAM,
        channel_id="channel-a",
        user_id="user-a",
        message_id=message_id,
        text_preview="hello",
    )


def test_worker_stub_emits_outbound_and_acks_ingress(
    require_integration: None,
    admin_session_factory: sessionmaker[Session],
) -> None:
    del require_integration
    settings = Settings(redis_url=get_settings().redis_url, redis_consumer_block_ms=100)
    redis = create_redis_client(settings)
    ingress_stream = f"test:ingress:{uuid4()}"
    outbound_stream = f"test:outbound:{uuid4()}"
    group = f"workers:{uuid4()}"
    outbound_group = f"outbound:{uuid4()}"
    envelope = stream_envelope(tenant_id=create_tenant(admin_session_factory))
    consumer = RedisStreamConsumer(redis=redis, settings=settings)

    try:
        RedisStreamPublisher(redis=redis, settings=settings).publish(
            stream=ingress_stream,
            envelope=envelope,
        )
        processed = MessageStubWorker(redis=redis, settings=settings).run_once(
            ingress_stream=ingress_stream,
            outbound_stream=outbound_stream,
            group=group,
            consumer="worker-a",
        )
        consumer.create_group(stream=outbound_stream, group=outbound_group)
        outbound = consumer.read_outbound_group(
            stream=outbound_stream,
            group=outbound_group,
            consumer="assertion",
        )
        pending = redis.xpending(ingress_stream, group)["pending"]

    finally:
        redis.delete(ingress_stream)
        redis.delete(outbound_stream)

    assert processed == 1
    assert pending == 0
    assert len(outbound) == 1
    assert outbound[0].payload.direction == MessageDirection.OUTBOUND
    assert outbound[0].payload.trace_id == envelope.trace_id
    assert outbound[0].payload.inbound_chat_event_id == envelope.chat_event_id


def test_worker_stub_leaves_ingress_pending_when_outbound_publish_fails(
    require_integration: None,
    admin_session_factory: sessionmaker[Session],
) -> None:
    del require_integration
    settings = Settings(redis_url=get_settings().redis_url, redis_consumer_block_ms=100)
    redis = create_redis_client(settings)
    ingress_stream = f"test:ingress:{uuid4()}"
    outbound_stream = f"test:outbound:{uuid4()}"
    group = f"workers:{uuid4()}"

    class RejectingPublisher:
        def publish(self, *, stream: str, envelope: object, group: str | None = None) -> str:
            del stream, envelope, group
            raise ServiceError(code="QUEUE_BACKPRESSURE", message="queue full", status_code=503)

    try:
        RedisStreamPublisher(redis=redis, settings=settings).publish(
            stream=ingress_stream,
            envelope=stream_envelope(tenant_id=create_tenant(admin_session_factory)),
        )

        with pytest.raises(ServiceError):
            MessageStubWorker(
                redis=redis,
                settings=settings,
                publisher=RejectingPublisher(),
            ).run_once(
                ingress_stream=ingress_stream,
                outbound_stream=outbound_stream,
                group=group,
                consumer="worker-a",
            )

        pending = redis.xpending(ingress_stream, group)["pending"]

    finally:
        redis.delete(ingress_stream)
        redis.delete(outbound_stream)

    assert pending == 1


def test_worker_stub_rejects_inactive_tenant_before_processing(
    require_integration: None,
    admin_session_factory: sessionmaker[Session],
) -> None:
    del require_integration
    settings = Settings(redis_url=get_settings().redis_url, redis_consumer_block_ms=100)
    redis = create_redis_client(settings)
    ingress_stream = f"test:ingress:{uuid4()}"
    outbound_stream = f"test:outbound:{uuid4()}"
    group = f"workers:{uuid4()}"
    tenant_id = create_tenant(admin_session_factory, status="disabled")

    try:
        RedisStreamPublisher(redis=redis, settings=settings).publish(
            stream=ingress_stream,
            envelope=stream_envelope(tenant_id=tenant_id),
        )

        with pytest.raises(ServiceError) as exc_info:
            MessageStubWorker(redis=redis, settings=settings).run_once(
                ingress_stream=ingress_stream,
                outbound_stream=outbound_stream,
                group=group,
                consumer="worker-a",
            )

        pending = redis.xpending(ingress_stream, group)["pending"]

    finally:
        redis.delete(ingress_stream)
        redis.delete(outbound_stream)

    assert exc_info.value.code == "TENANT_INACTIVE"
    assert pending == 1
    assert redis.xlen(outbound_stream) == 0


def test_worker_stub_continues_batch_after_inactive_tenant(
    require_integration: None,
    admin_session_factory: sessionmaker[Session],
) -> None:
    del require_integration
    settings = Settings(redis_url=get_settings().redis_url, redis_consumer_block_ms=100)
    redis = create_redis_client(settings)
    ingress_stream = f"test:ingress:{uuid4()}"
    outbound_stream = f"test:outbound:{uuid4()}"
    group = f"workers:{uuid4()}"
    outbound_group = f"outbound:{uuid4()}"
    inactive_tenant_id = create_tenant(admin_session_factory, status="disabled")
    active_tenant_id = create_tenant(admin_session_factory)

    try:
        publisher = RedisStreamPublisher(redis=redis, settings=settings)
        publisher.publish(
            stream=ingress_stream,
            envelope=stream_envelope(tenant_id=inactive_tenant_id, message_id="message-disabled"),
        )
        publisher.publish(
            stream=ingress_stream,
            envelope=stream_envelope(tenant_id=active_tenant_id, message_id="message-active"),
        )

        with pytest.raises(ServiceError) as exc_info:
            MessageStubWorker(redis=redis, settings=settings).run_once(
                ingress_stream=ingress_stream,
                outbound_stream=outbound_stream,
                group=group,
                consumer="worker-a",
            )

        pending = redis.xpending(ingress_stream, group)["pending"]
        consumer = RedisStreamConsumer(redis=redis, settings=settings)
        consumer.create_group(stream=outbound_stream, group=outbound_group)
        outbound = consumer.read_outbound_group(
            stream=outbound_stream,
            group=outbound_group,
            consumer="assertion",
        )

    finally:
        redis.delete(ingress_stream)
        redis.delete(outbound_stream)

    assert exc_info.value.code == "TENANT_INACTIVE"
    assert pending == 1
    assert len(outbound) == 1
    assert outbound[0].payload.tenant_id == active_tenant_id
    assert outbound[0].payload.reply_to_message_id == "message-active"
