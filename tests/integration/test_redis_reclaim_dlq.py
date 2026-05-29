import os
from collections.abc import Iterator
from typing import cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from core.api.schemas.messages import MessageDirection, Platform, StreamMessageEnvelope
from core.config import Settings, get_settings
from core.streams.consumer import RedisStreamConsumer
from core.streams.dlq import DlqMessageEnvelope
from core.streams.names import StreamDirection, stream_name
from core.streams.publisher import RedisStreamPublisher
from core.streams.redis_client import create_redis_client
from core.workers.message_reclaim import MessageReclaimWorker

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
                "slug": f"tenant-reclaim-{tenant_id}",
                "status": status,
            },
        )
    return tenant_id


def stream_envelope(tenant_id: UUID) -> StreamMessageEnvelope:
    return StreamMessageEnvelope(
        trace_id=uuid4(),
        tenant_id=tenant_id,
        chat_event_id=uuid4(),
        direction=MessageDirection.INBOUND,
        platform=Platform.TELEGRAM,
        channel_id="channel-a",
        user_id="user-a",
        message_id="message-a",
        text_preview="hello",
    )


def test_reclaim_worker_reprocesses_stale_pending_and_acks(
    require_integration: None,
    admin_session_factory: sessionmaker[Session],
) -> None:
    del require_integration
    settings = Settings(
        redis_url=get_settings().redis_url,
        redis_consumer_block_ms=100,
        redis_reclaim_idle_millis=0,
        redis_reclaim_retry_limit=3,
    )
    redis = create_redis_client(settings)
    tenant_id = create_tenant(admin_session_factory)
    ingress_stream = f"test:reclaim:ingress:{uuid4()}"
    outbound_stream = f"test:reclaim:outbound:{uuid4()}"
    dlq_stream = stream_name(
        environment="test",
        tenant_scope=str(tenant_id),
        direction=StreamDirection.DLQ,
        platform=Platform.TELEGRAM,
    )
    group = f"workers:{uuid4()}"
    outbound_group = f"outbound:{uuid4()}"
    consumer = RedisStreamConsumer(redis=redis, settings=settings)

    try:
        consumer.create_group(stream=ingress_stream, group=group)
        RedisStreamPublisher(redis=redis, settings=settings).publish(
            stream=ingress_stream,
            envelope=stream_envelope(tenant_id),
        )
        assert consumer.read_group(stream=ingress_stream, group=group, consumer="crashed")

        result = MessageReclaimWorker(redis=redis, settings=settings).run_once(
            ingress_stream=ingress_stream,
            outbound_stream=outbound_stream,
            dlq_stream=dlq_stream,
            group=group,
            consumer="reclaimer",
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
        redis.delete(dlq_stream)

    assert result.reclaimed == 1
    assert result.processed == 1
    assert result.moved_to_dlq == 0
    assert pending == 0
    assert len(outbound) == 1
    assert outbound[0].payload.inbound_chat_event_id


def test_reclaim_worker_moves_retry_exceeded_to_dlq_then_acks(
    require_integration: None,
    admin_session_factory: sessionmaker[Session],
) -> None:
    del require_integration
    settings = Settings(
        redis_url=get_settings().redis_url,
        redis_consumer_block_ms=100,
        redis_reclaim_idle_millis=0,
        redis_reclaim_retry_limit=1,
        redis_dlq_max_length=25,
    )
    redis = create_redis_client(settings)
    tenant_id = create_tenant(admin_session_factory)
    ingress_stream = f"test:reclaim:ingress:{uuid4()}"
    outbound_stream = f"test:reclaim:outbound:{uuid4()}"
    dlq_stream = f"test:reclaim:dlq:{uuid4()}"
    group = f"workers:{uuid4()}"
    consumer = RedisStreamConsumer(redis=redis, settings=settings)

    try:
        consumer.create_group(stream=ingress_stream, group=group)
        RedisStreamPublisher(redis=redis, settings=settings).publish(
            stream=ingress_stream,
            envelope=stream_envelope(tenant_id),
        )
        assert consumer.read_group(stream=ingress_stream, group=group, consumer="crashed")

        result = MessageReclaimWorker(redis=redis, settings=settings).run_once(
            ingress_stream=ingress_stream,
            outbound_stream=outbound_stream,
            dlq_stream=dlq_stream,
            group=group,
            consumer="reclaimer",
        )
        pending = redis.xpending(ingress_stream, group)["pending"]
        dlq_rows = cast(list[tuple[str, dict[str, str]]], redis.xrange(dlq_stream))
        dlq_payload = DlqMessageEnvelope.model_validate_json(dlq_rows[0][1]["payload"])

    finally:
        redis.delete(ingress_stream)
        redis.delete(outbound_stream)
        redis.delete(dlq_stream)

    assert result.reclaimed == 1
    assert result.processed == 0
    assert result.moved_to_dlq == 1
    assert pending == 0
    assert dlq_payload.tenant_id == tenant_id
    assert dlq_payload.platform == Platform.TELEGRAM
    assert dlq_payload.original_stream_id
    assert dlq_payload.failure_class == "RETRY_LIMIT_EXCEEDED"
