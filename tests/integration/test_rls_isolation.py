import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
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


def test_tenant_plugins_rls_blocks_cross_tenant_reads_and_writes(
    admin_session_factory: sessionmaker[Session],
    app_session_factory: sessionmaker[Session],
) -> None:
    tenant_a = uuid4()
    tenant_b = uuid4()
    plugin_a = uuid4()
    plugin_b = uuid4()

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
                "slug_a": f"tenant-plugin-a-{tenant_a}",
                "tenant_b": tenant_b,
                "slug_b": f"tenant-plugin-b-{tenant_b}",
            },
        )
        session.execute(
            text(
                """
                INSERT INTO tenant_plugins (id, tenant_id, plugin_name, enabled, config)
                VALUES
                    (:plugin_a, :tenant_a, 'rag.search', true, '{}'),
                    (:plugin_b, :tenant_b, 'web.search', true, '{}')
                """
            ),
            {
                "plugin_a": plugin_a,
                "tenant_a": tenant_a,
                "plugin_b": plugin_b,
                "tenant_b": tenant_b,
            },
        )

    with tenant_session(tenant_a, app_session_factory) as session:
        rows = [
            (row[0], row[1])
            for row in session.execute(
                text("SELECT tenant_id, plugin_name FROM tenant_plugins ORDER BY plugin_name")
            ).all()
        ]

    assert rows == [(tenant_a, "rag.search")]

    with pytest.raises(DBAPIError), tenant_session(tenant_a, app_session_factory) as session:
        session.execute(
            text(
                """
                    INSERT INTO tenant_plugins (id, tenant_id, plugin_name, enabled, config)
                    VALUES (:plugin_id, :tenant_b, 'crypto.price', true, '{}')
                    """
            ),
            {"plugin_id": uuid4(), "tenant_b": tenant_b},
        )


def test_tenant_plugins_rls_fails_closed_without_tenant_context(
    admin_session_factory: sessionmaker[Session],
    app_session_factory: sessionmaker[Session],
) -> None:
    tenant_id = uuid4()

    with admin_session_factory() as session, session.begin():
        session.execute(
            text("INSERT INTO tenants (id, slug, status) VALUES (:id, :slug, 'active')"),
            {"id": tenant_id, "slug": f"tenant-plugin-missing-context-{tenant_id}"},
        )
        session.execute(
            text(
                """
                INSERT INTO tenant_plugins (id, tenant_id, plugin_name, enabled, config)
                VALUES (:plugin_id, :tenant_id, 'rag.search', true, '{}')
                """
            ),
            {"plugin_id": uuid4(), "tenant_id": tenant_id},
        )

    with app_session_factory() as session:
        rows = [row[0] for row in session.execute(text("SELECT id FROM tenant_plugins")).all()]

    assert rows == []


def test_tenant_platforms_rls_blocks_cross_tenant_reads_and_writes(
    admin_session_factory: sessionmaker[Session],
    app_session_factory: sessionmaker[Session],
) -> None:
    tenant_a = uuid4()
    tenant_b = uuid4()
    platform_a = uuid4()
    platform_b = uuid4()
    workspace_a = f"workspace-a-{platform_a}"
    channel_a = f"channel-a-{platform_a}"
    workspace_b = f"workspace-b-{platform_b}"
    channel_b = f"channel-b-{platform_b}"

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
                "slug_a": f"tenant-platform-a-{tenant_a}",
                "tenant_b": tenant_b,
                "slug_b": f"tenant-platform-b-{tenant_b}",
            },
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
                        :platform_a, :tenant_a, 'telegram', :workspace_a,
                        :channel_a, 'active', '{}'
                    ),
                    (
                        :platform_b, :tenant_b, 'discord', :workspace_b,
                        :channel_b, 'active', '{}'
                    )
                """
            ),
            {
                "platform_a": platform_a,
                "tenant_a": tenant_a,
                "workspace_a": workspace_a,
                "channel_a": channel_a,
                "platform_b": platform_b,
                "tenant_b": tenant_b,
                "workspace_b": workspace_b,
                "channel_b": channel_b,
            },
        )

    with tenant_session(tenant_a, app_session_factory) as session:
        rows = [
            (row[0], row[1], row[2])
            for row in session.execute(
                text(
                    """
                    SELECT tenant_id, platform, external_channel_id
                    FROM tenant_platforms
                    ORDER BY platform
                    """
                )
            ).all()
        ]

    assert rows == [(tenant_a, "telegram", channel_a)]

    with pytest.raises(DBAPIError), tenant_session(tenant_a, app_session_factory) as session:
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
                        :platform_id, :tenant_b, 'telegram', 'workspace-c',
                        'channel-c', 'active', '{}'
                    )
                """
            ),
            {"platform_id": uuid4(), "tenant_b": tenant_b},
        )


def test_tenant_platforms_rls_fails_closed_without_tenant_context(
    admin_session_factory: sessionmaker[Session],
    app_session_factory: sessionmaker[Session],
) -> None:
    tenant_id = uuid4()
    platform_id = uuid4()

    with admin_session_factory() as session, session.begin():
        session.execute(
            text("INSERT INTO tenants (id, slug, status) VALUES (:id, :slug, 'active')"),
            {"id": tenant_id, "slug": f"tenant-platform-missing-context-{tenant_id}"},
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
                "workspace_id": f"workspace-a-{platform_id}",
                "channel_id": f"channel-a-{platform_id}",
            },
        )

    with app_session_factory() as session:
        rows = [row[0] for row in session.execute(text("SELECT id FROM tenant_platforms")).all()]

    assert rows == []


def test_stream_outbox_rls_blocks_cross_tenant_reads_and_writes(
    admin_session_factory: sessionmaker[Session],
    app_session_factory: sessionmaker[Session],
) -> None:
    tenant_a = uuid4()
    tenant_b = uuid4()
    event_a = uuid4()
    event_b = uuid4()
    outbox_a = uuid4()
    outbox_b = uuid4()

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
                "slug_a": f"tenant-outbox-a-{tenant_a}",
                "tenant_b": tenant_b,
                "slug_b": f"tenant-outbox-b-{tenant_b}",
            },
        )
        session.execute(
            text(
                """
                INSERT INTO chat_events
                    (
                        id, tenant_id, trace_id, platform, channel_id, user_id,
                        message_id, text, direction
                    )
                VALUES
                    (
                        :event_a, :tenant_a, :trace_a, 'telegram', 'chan', 'user',
                        'msg-a', 'hello a', 'inbound'
                    ),
                    (
                        :event_b, :tenant_b, :trace_b, 'telegram', 'chan', 'user',
                        'msg-b', 'hello b', 'inbound'
                    )
                """
            ),
            {
                "event_a": event_a,
                "tenant_a": tenant_a,
                "trace_a": uuid4(),
                "event_b": event_b,
                "tenant_b": tenant_b,
                "trace_b": uuid4(),
            },
        )
        session.execute(
            text(
                """
                INSERT INTO stream_outbox
                    (id, tenant_id, chat_event_id, stream_name, payload, status)
                VALUES
                    (
                        :outbox_a, :tenant_a, :event_a, :stream_a,
                        '{"trace_id":"a"}', 'pending'
                    ),
                    (
                        :outbox_b, :tenant_b, :event_b, :stream_b,
                        '{"trace_id":"b"}', 'pending'
                    )
                """
            ),
            {
                "outbox_a": outbox_a,
                "tenant_a": tenant_a,
                "event_a": event_a,
                "stream_a": f"local:{tenant_a}:ingress:telegram",
                "outbox_b": outbox_b,
                "tenant_b": tenant_b,
                "event_b": event_b,
                "stream_b": f"local:{tenant_b}:ingress:telegram",
            },
        )

    with tenant_session(tenant_a, app_session_factory) as session:
        rows = [
            (row[0], row[1])
            for row in session.execute(
                text("SELECT tenant_id, stream_name FROM stream_outbox ORDER BY stream_name")
            ).all()
        ]

    assert rows == [(tenant_a, f"local:{tenant_a}:ingress:telegram")]

    with pytest.raises(DBAPIError), tenant_session(tenant_a, app_session_factory) as session:
        session.execute(
            text(
                """
                INSERT INTO stream_outbox
                    (id, tenant_id, chat_event_id, stream_name, payload, status)
                VALUES
                    (
                        :outbox_id, :tenant_b, :event_b,
                        'local:blocked:ingress:telegram', '{}', 'pending'
                    )
                """
            ),
            {"outbox_id": uuid4(), "tenant_b": tenant_b, "event_b": event_b},
        )


def test_stream_outbox_rls_fails_closed_without_tenant_context(
    admin_session_factory: sessionmaker[Session],
    app_session_factory: sessionmaker[Session],
) -> None:
    tenant_id = uuid4()
    event_id = uuid4()
    outbox_id = uuid4()

    with admin_session_factory() as session, session.begin():
        session.execute(
            text("INSERT INTO tenants (id, slug, status) VALUES (:id, :slug, 'active')"),
            {"id": tenant_id, "slug": f"tenant-outbox-missing-context-{tenant_id}"},
        )
        session.execute(
            text(
                """
                INSERT INTO chat_events
                    (
                        id, tenant_id, trace_id, platform, channel_id, user_id,
                        message_id, text, direction
                    )
                VALUES
                    (
                        :event_id, :tenant_id, :trace_id, 'telegram', 'chan', 'user',
                        'msg', 'hidden', 'inbound'
                    )
                """
            ),
            {"event_id": event_id, "tenant_id": tenant_id, "trace_id": uuid4()},
        )
        session.execute(
            text(
                """
                INSERT INTO stream_outbox
                    (id, tenant_id, chat_event_id, stream_name, payload, status)
                VALUES
                    (:outbox_id, :tenant_id, :event_id, :stream_name, '{}', 'pending')
                """
            ),
            {
                "outbox_id": outbox_id,
                "tenant_id": tenant_id,
                "event_id": event_id,
                "stream_name": f"local:{tenant_id}:ingress:telegram",
            },
        )

    with app_session_factory() as session:
        rows = [row[0] for row in session.execute(text("SELECT id FROM stream_outbox")).all()]

    assert rows == []
