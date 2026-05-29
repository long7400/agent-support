import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from core.api.schemas.messages import Platform
from core.config import get_settings
from core.persistence.repositories.chat_events import ChatEventRepository

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def require_integration() -> None:
    if os.getenv("AGENT_SUPPORT_RUN_INTEGRATION") != "1":
        pytest.skip("set AGENT_SUPPORT_RUN_INTEGRATION=1 to run integration tests")


@pytest.fixture(scope="module")
def admin_session_factory(require_integration: None) -> sessionmaker[Session]:
    del require_integration
    engine = create_engine(get_settings().database_admin_url, pool_pre_ping=True)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def test_chat_event_repository_reuses_existing_inbound_message(
    admin_session_factory: sessionmaker[Session],
) -> None:
    tenant_id = uuid4()
    trace_id = uuid4()

    with admin_session_factory() as session, session.begin():
        session.execute(
            text("INSERT INTO tenants (id, slug, status) VALUES (:id, :slug, 'active')"),
            {"id": tenant_id, "slug": f"tenant-message-ingest-{tenant_id}"},
        )
        repository = ChatEventRepository(session)

        created_first, first = repository.insert_inbound_idempotent(
            tenant_id=tenant_id,
            trace_id=trace_id,
            platform=Platform.TELEGRAM,
            channel_id="channel-a",
            user_id="user-a",
            message_id="message-a",
            text="hello",
            thread_id=None,
        )
        created_second, second = repository.insert_inbound_idempotent(
            tenant_id=tenant_id,
            trace_id=uuid4(),
            platform=Platform.TELEGRAM,
            channel_id="channel-a",
            user_id="user-a",
            message_id="message-a",
            text="duplicate should not overwrite",
            thread_id=None,
        )

        row_count = session.execute(
            text(
                """
                SELECT count(*)
                FROM chat_events
                WHERE tenant_id = :tenant_id
                  AND platform = 'telegram'
                  AND channel_id = 'channel-a'
                  AND message_id = 'message-a'
                  AND direction = 'inbound'
                """
            ),
            {"tenant_id": tenant_id},
        ).scalar_one()

    assert created_first is True
    assert created_second is False
    assert second.id == first.id
    assert first.trace_id == trace_id
    assert row_count == 1
