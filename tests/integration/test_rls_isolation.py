import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from core.config import get_settings
from core.persistence.rls import tenant_session

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


@pytest.fixture(scope="module")
def app_session_factory(require_integration: None) -> sessionmaker[Session]:
    del require_integration
    engine = create_engine(get_settings().database_url, pool_pre_ping=True)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def test_rls_blocks_cross_tenant_reads(
    admin_session_factory: sessionmaker[Session],
    app_session_factory: sessionmaker[Session],
) -> None:
    tenant_a = uuid4()
    tenant_b = uuid4()
    trace_a = uuid4()
    trace_b = uuid4()

    with admin_session_factory() as session, session.begin():
        session.execute(
            text(
                """
                INSERT INTO tenants (id, slug, status)
                VALUES (:tenant_a, :slug_a, 'active'), (:tenant_b, :slug_b, 'active')
                """
            ),
            {
                "tenant_a": tenant_a,
                "slug_a": f"tenant-a-{tenant_a}",
                "tenant_b": tenant_b,
                "slug_b": f"tenant-b-{tenant_b}",
            },
        )
        session.execute(
            text(
                """
                INSERT INTO chat_events
                    (id, tenant_id, trace_id, platform, channel_id, user_id, message_id, text)
                VALUES
                    (
                        :event_a, :tenant_a, :trace_a, 'telegram', 'chan', 'user',
                        'msg-a', 'hello a'
                    ),
                    (
                        :event_b, :tenant_b, :trace_b, 'telegram', 'chan', 'user',
                        'msg-b', 'hello b'
                    )
                """
            ),
            {
                "event_a": uuid4(),
                "tenant_a": tenant_a,
                "trace_a": trace_a,
                "event_b": uuid4(),
                "tenant_b": tenant_b,
                "trace_b": trace_b,
            },
        )

    with tenant_session(tenant_a, app_session_factory) as session:
        rows = [
            (row[0], row[1], row[2])
            for row in session.execute(
                text("SELECT tenant_id, trace_id, text FROM chat_events ORDER BY message_id")
            ).all()
        ]
        tenant_rows = [
            row[0] for row in session.execute(text("SELECT id FROM tenants ORDER BY slug")).all()
        ]

    assert rows == [(tenant_a, trace_a, "hello a")]
    assert tenant_rows == [tenant_a]


def test_rls_fails_closed_without_tenant_context(
    admin_session_factory: sessionmaker[Session],
    app_session_factory: sessionmaker[Session],
) -> None:
    tenant_id = uuid4()

    with admin_session_factory() as session, session.begin():
        session.execute(
            text("INSERT INTO tenants (id, slug, status) VALUES (:id, :slug, 'active')"),
            {"id": tenant_id, "slug": f"tenant-missing-context-{tenant_id}"},
        )
        session.execute(
            text(
                """
                INSERT INTO chat_events
                    (id, tenant_id, trace_id, platform, channel_id, user_id, message_id, text)
                VALUES
                    (
                        :event_id, :tenant_id, :trace_id, 'telegram', 'chan', 'user',
                        'msg', 'hidden'
                    )
                """
            ),
            {"event_id": uuid4(), "tenant_id": tenant_id, "trace_id": uuid4()},
        )

    with app_session_factory() as session:
        chat_rows = [row[0] for row in session.execute(text("SELECT id FROM chat_events")).all()]
        tenant_rows = [row[0] for row in session.execute(text("SELECT id FROM tenants")).all()]

    assert chat_rows == []
    assert tenant_rows == []
