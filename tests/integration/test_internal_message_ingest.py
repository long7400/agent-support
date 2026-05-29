import json
import os
from collections.abc import Iterator
from typing import Any, cast
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from core.api.main import create_app
from core.api.routes.internal_messages import get_stream_publisher
from core.api.schemas.messages import Platform
from core.config import get_settings
from core.services.errors import ServiceError
from core.streams.names import StreamDirection, stream_name
from core.streams.redis_client import create_redis_client

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def require_integration() -> None:
    if os.getenv("AGENT_SUPPORT_RUN_INTEGRATION") != "1":
        pytest.skip("set AGENT_SUPPORT_RUN_INTEGRATION=1 to run integration tests")


@pytest.fixture()
def client(require_integration: None) -> Iterator[TestClient]:
    del require_integration
    get_settings.cache_clear()
    app = create_app()
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def admin_session_factory(require_integration: None) -> sessionmaker[Session]:
    del require_integration
    engine = create_engine(get_settings().database_admin_url, pool_pre_ping=True)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def register_platform(
    admin_session_factory: sessionmaker[Session],
    *,
    workspace_id: str,
    channel_id: str,
) -> object:
    tenant_id = uuid4()
    platform_id = uuid4()
    with admin_session_factory() as session, session.begin():
        session.execute(
            text("INSERT INTO tenants (id, slug, status) VALUES (:id, :slug, 'active')"),
            {"id": tenant_id, "slug": f"tenant-internal-ingest-{tenant_id}"},
        )
        session.execute(
            text(
                """
                INSERT INTO tenant_platforms
                    (
                        id, tenant_id, platform, external_workspace_id,
                        external_channel_id, status, config
                    )
                VALUES
                    (
                        :platform_id, :tenant_id, 'telegram', :workspace_id,
                        :channel_id, 'active', '{}'
                    )
                """
            ),
            {
                "platform_id": platform_id,
                "tenant_id": tenant_id,
                "workspace_id": workspace_id,
                "channel_id": channel_id,
            },
        )
    return tenant_id


def ingest_payload(*, workspace_id: str, channel_id: str, message_id: str) -> dict[str, str]:
    return {
        "trace_id": str(uuid4()),
        "platform": "telegram",
        "external_workspace_id": workspace_id,
        "channel_id": channel_id,
        "user_id": "user-a",
        "message_id": message_id,
        "text": "hello from adapter",
    }


def test_internal_ingest_accepts_and_publishes_once(
    client: TestClient,
    admin_session_factory: sessionmaker[Session],
) -> None:
    workspace_id = f"workspace-{uuid4()}"
    channel_id = f"channel-{uuid4()}"
    tenant_id = register_platform(
        admin_session_factory,
        workspace_id=workspace_id,
        channel_id=channel_id,
    )
    redis = create_redis_client(get_settings())
    ingress_stream = stream_name(
        environment=get_settings().environment,
        tenant_scope=str(tenant_id),
        direction=StreamDirection.INGRESS,
        platform=Platform.TELEGRAM,
    )
    redis.delete(ingress_stream)

    response = client.post(
        "/internal/messages/ingest",
        headers={"X-Internal-Token": get_settings().internal_token},
        json=ingest_payload(
            workspace_id=workspace_id,
            channel_id=channel_id,
            message_id="message-a",
        ),
    )

    assert response.status_code == 202
    assert response.json()["status"] == "accepted"
    assert response.headers["X-Trace-Id"] == response.json()["trace_id"]
    assert redis.xlen(ingress_stream) == 1


def test_internal_ingest_duplicate_does_not_republish(
    client: TestClient,
    admin_session_factory: sessionmaker[Session],
) -> None:
    workspace_id = f"workspace-{uuid4()}"
    channel_id = f"channel-{uuid4()}"
    tenant_id = register_platform(
        admin_session_factory,
        workspace_id=workspace_id,
        channel_id=channel_id,
    )
    redis = create_redis_client(get_settings())
    ingress_stream = stream_name(
        environment=get_settings().environment,
        tenant_scope=str(tenant_id),
        direction=StreamDirection.INGRESS,
        platform=Platform.TELEGRAM,
    )
    redis.delete(ingress_stream)
    payload = ingest_payload(
        workspace_id=workspace_id,
        channel_id=channel_id,
        message_id="message-duplicate",
    )

    first = client.post(
        "/internal/messages/ingest",
        headers={"X-Internal-Token": get_settings().internal_token},
        json=payload,
    )
    second = client.post(
        "/internal/messages/ingest",
        headers={"X-Internal-Token": get_settings().internal_token},
        json=payload,
    )

    with admin_session_factory() as session:
        row_count = session.execute(
            text(
                """
                SELECT count(*)
                FROM chat_events
                WHERE tenant_id = :tenant_id
                  AND message_id = 'message-duplicate'
                  AND direction = 'inbound'
                """
            ),
            {"tenant_id": tenant_id},
        ).scalar_one()

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["chat_event_id"] == second.json()["chat_event_id"]
    assert redis.xlen(ingress_stream) == 1
    assert row_count == 1


def test_internal_ingest_rejects_unknown_platform_mapping(client: TestClient) -> None:
    response = client.post(
        "/internal/messages/ingest",
        headers={"X-Internal-Token": get_settings().internal_token},
        json=ingest_payload(
            workspace_id=f"missing-{uuid4()}",
            channel_id=f"missing-{uuid4()}",
            message_id="message-a",
        ),
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TENANT_PLATFORM_NOT_FOUND"


def test_internal_ingest_backpressure_keeps_pending_outbox_for_retry(
    client: TestClient,
    admin_session_factory: sessionmaker[Session],
) -> None:
    workspace_id = f"workspace-{uuid4()}"
    channel_id = f"channel-{uuid4()}"
    tenant_id = register_platform(
        admin_session_factory,
        workspace_id=workspace_id,
        channel_id=channel_id,
    )
    redis = create_redis_client(get_settings())
    ingress_stream = stream_name(
        environment=get_settings().environment,
        tenant_scope=str(tenant_id),
        direction=StreamDirection.INGRESS,
        platform=Platform.TELEGRAM,
    )
    redis.delete(ingress_stream)

    class RejectingPublisher:
        def publish(self, *, stream: str, envelope: object, group: str | None = None) -> str:
            del stream, envelope, group
            raise ServiceError(
                code="QUEUE_BACKPRESSURE",
                message="queue full",
                status_code=503,
            )

    cast(Any, client.app).dependency_overrides[get_stream_publisher] = lambda: RejectingPublisher()
    payload = ingest_payload(
        workspace_id=workspace_id,
        channel_id=channel_id,
        message_id="message-backpressure",
    )

    response = client.post(
        "/internal/messages/ingest",
        headers={"X-Internal-Token": get_settings().internal_token},
        json=payload,
    )

    with admin_session_factory() as session:
        row_count = session.execute(
            text(
                """
                SELECT count(*)
                FROM chat_events
                WHERE tenant_id = :tenant_id AND message_id = 'message-backpressure'
                """
            ),
            {"tenant_id": tenant_id},
        ).scalar_one()
        pending_count = session.execute(
            text(
                """
                SELECT count(*)
                FROM stream_outbox
                WHERE tenant_id = :tenant_id AND status = 'pending'
                """
            ),
            {"tenant_id": tenant_id},
        ).scalar_one()
        last_error = session.execute(
            text(
                """
                SELECT last_error
                FROM stream_outbox
                WHERE tenant_id = :tenant_id AND status = 'pending'
                """
            ),
            {"tenant_id": tenant_id},
        ).scalar_one()

    cast(Any, client.app).dependency_overrides.clear()
    retry = client.post(
        "/internal/messages/ingest",
        headers={"X-Internal-Token": get_settings().internal_token},
        json=payload,
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "QUEUE_BACKPRESSURE"
    assert row_count == 1
    assert pending_count == 1
    assert last_error == "queue full"
    assert retry.status_code == 202
    assert redis.xlen(ingress_stream) == 1


def test_internal_ingest_publisher_receives_ingress_consumer_group(
    client: TestClient,
    admin_session_factory: sessionmaker[Session],
) -> None:
    workspace_id = f"workspace-{uuid4()}"
    channel_id = f"channel-{uuid4()}"
    register_platform(
        admin_session_factory,
        workspace_id=workspace_id,
        channel_id=channel_id,
    )

    class CapturingPublisher:
        def __init__(self) -> None:
            self.group: str | None = None

        def publish(self, *, stream: str, envelope: object, group: str | None = None) -> str:
            del stream, envelope
            self.group = group
            return "1-0"

    publisher = CapturingPublisher()
    cast(Any, client.app).dependency_overrides[get_stream_publisher] = lambda: publisher

    response = client.post(
        "/internal/messages/ingest",
        headers={"X-Internal-Token": get_settings().internal_token},
        json=ingest_payload(
            workspace_id=workspace_id,
            channel_id=channel_id,
            message_id="message-group",
        ),
    )

    assert response.status_code == 202
    assert publisher.group == get_settings().redis_ingress_consumer_group


def test_internal_ingest_rejects_request_supplied_tenant_id(client: TestClient) -> None:
    payload = ingest_payload(
        workspace_id=f"workspace-{uuid4()}",
        channel_id=f"channel-{uuid4()}",
        message_id="message-a",
    )
    payload["tenant_id"] = str(uuid4())

    response = client.post(
        "/internal/messages/ingest",
        headers={"X-Internal-Token": get_settings().internal_token},
        json=payload,
    )

    assert response.status_code == 422
    errors = json.dumps(response.json()["error"]["details"]["errors"])
    assert "tenant_id" in errors
