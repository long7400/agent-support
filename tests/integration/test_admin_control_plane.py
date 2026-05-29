import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from core.api.main import create_app
from core.config import get_settings
from core.persistence.models import TenantPlugin
from core.persistence.repositories.tenant_plugins import TenantPluginRepository

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def client() -> TestClient:
    if os.getenv("AGENT_SUPPORT_RUN_INTEGRATION") != "1":
        pytest.skip("set AGENT_SUPPORT_RUN_INTEGRATION=1 to run integration tests")
    get_settings.cache_clear()
    return TestClient(create_app())


@pytest.fixture(scope="module")
def admin_session_factory() -> sessionmaker[Session]:
    engine = create_engine(get_settings().database_admin_url, pool_pre_ping=True)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def test_admin_create_update_plugin_and_audit(
    client: TestClient,
    admin_session_factory: sessionmaker[Session],
) -> None:
    trace_id = str(uuid4())
    slug = f"tenant-api-{uuid4()}"
    headers = {
        "X-Admin-Token": get_settings().admin_token,
        "X-Trace-Id": trace_id,
    }

    created = client.post(
        "/admin/tenants",
        headers=headers,
        json={
            "slug": slug,
            "display_name": "Tenant API",
            "config": {"persona": "helpful"},
        },
    )

    assert created.status_code == 201
    tenant_id = created.json()["id"]
    assert created.headers["x-trace-id"] == trace_id

    updated = client.patch(
        f"/admin/tenants/{tenant_id}",
        headers=headers,
        json={
            "display_name": "Tenant API Updated",
            "config": {"persona": "precise"},
        },
    )
    assert updated.status_code == 200
    assert updated.json()["config_version"] == 2

    enabled = client.put(
        f"/admin/tenants/{tenant_id}/plugins/rag.search",
        headers=headers,
        json={"config": {"top_k": 5}},
    )
    assert enabled.status_code == 200
    assert enabled.json()["enabled"] is True

    with admin_session_factory() as session:
        actions = [
            row[0]
            for row in session.execute(
                text(
                    """
                    SELECT action
                    FROM audit_log
                    WHERE tenant_id = :tenant_id
                    ORDER BY created_at
                    """
                ),
                {"tenant_id": tenant_id},
            ).all()
        ]

    assert actions == ["tenant.created", "tenant.updated", "tenant_plugin.enabled"]


def test_admin_patch_tenant_preserves_omitted_config(client: TestClient) -> None:
    trace_id = str(uuid4())
    slug = f"tenant-patch-{uuid4()}"
    headers = {
        "X-Admin-Token": get_settings().admin_token,
        "X-Trace-Id": trace_id,
    }

    created = client.post(
        "/admin/tenants",
        headers=headers,
        json={
            "slug": slug,
            "display_name": "Tenant Patch",
            "config": {"persona": "original"},
        },
    )
    assert created.status_code == 201
    tenant_id = created.json()["id"]

    updated = client.patch(
        f"/admin/tenants/{tenant_id}",
        headers=headers,
        json={"display_name": "Tenant Patch Renamed"},
    )

    assert updated.status_code == 200
    assert updated.json()["display_name"] == "Tenant Patch Renamed"
    assert updated.json()["config"] == {"persona": "original"}


def test_admin_patch_tenant_rejects_empty_body_without_audit(
    client: TestClient,
    admin_session_factory: sessionmaker[Session],
) -> None:
    headers = {"X-Admin-Token": get_settings().admin_token}
    slug = f"tenant-empty-patch-{uuid4()}"

    created = client.post(
        "/admin/tenants",
        headers=headers,
        json={"slug": slug, "display_name": "Tenant Empty Patch", "config": {}},
    )
    assert created.status_code == 201
    tenant_id = created.json()["id"]

    response = client.patch(
        f"/admin/tenants/{tenant_id}",
        headers=headers,
        json={},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    with admin_session_factory() as session:
        actions = [
            row[0]
            for row in session.execute(
                text(
                    """
                    SELECT action
                    FROM audit_log
                    WHERE tenant_id = :tenant_id
                    ORDER BY created_at
                    """
                ),
                {"tenant_id": tenant_id},
            ).all()
        ]

    assert actions == ["tenant.created"]


def test_admin_enable_plugin_for_unknown_tenant_returns_not_found(client: TestClient) -> None:
    headers = {"X-Admin-Token": get_settings().admin_token}
    missing_tenant_id = uuid4()

    response = client.put(
        f"/admin/tenants/{missing_tenant_id}/plugins/rag.search",
        headers=headers,
        json={"config": {}},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TENANT_NOT_FOUND"


def test_tenant_plugin_upsert_handles_concurrent_duplicate_enable(
    client: TestClient,
    admin_session_factory: sessionmaker[Session],
) -> None:
    headers = {"X-Admin-Token": get_settings().admin_token}
    slug = f"tenant-plugin-concurrent-{uuid4()}"

    created = client.post(
        "/admin/tenants",
        headers=headers,
        json={"slug": slug, "display_name": "Tenant Plugin Concurrent", "config": {}},
    )
    assert created.status_code == 201
    tenant_id = created.json()["id"]
    barrier = Barrier(2)

    class ConcurrentTenantPluginRepository(TenantPluginRepository):
        def get(self, *, tenant_id: object, plugin_name: str) -> TenantPlugin | None:
            plugin = super().get(tenant_id=tenant_id, plugin_name=plugin_name)  # type: ignore[arg-type]
            if plugin is None:
                barrier.wait(timeout=5)
            return plugin

    def enable_plugin(top_k: int) -> None:
        with admin_session_factory() as session, session.begin():
            ConcurrentTenantPluginRepository(session).upsert_enabled(
                tenant_id=tenant_id,
                plugin_name="rag.search",
                config={"top_k": top_k},
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(enable_plugin, top_k) for top_k in (5, 7)]
        for future in futures:
            future.result()

    with admin_session_factory() as session:
        rows = session.execute(
            text(
                """
                SELECT enabled, config
                FROM tenant_plugins
                WHERE tenant_id = :tenant_id AND plugin_name = 'rag.search'
                """
            ),
            {"tenant_id": tenant_id},
        ).all()

    assert len(rows) == 1
    assert rows[0][0] is True
    assert rows[0][1]["top_k"] in {5, 7}


def test_admin_plugin_response_redacts_secret_like_config_keys(
    client: TestClient,
    admin_session_factory: sessionmaker[Session],
) -> None:
    headers = {"X-Admin-Token": get_settings().admin_token}
    slug = f"tenant-plugin-redact-{uuid4()}"

    created = client.post(
        "/admin/tenants",
        headers=headers,
        json={"slug": slug, "display_name": "Tenant Plugin Redact", "config": {}},
    )
    assert created.status_code == 201
    tenant_id = created.json()["id"]

    with admin_session_factory.begin() as session:
        session.add(
            TenantPlugin(
                tenant_id=tenant_id,
                plugin_name="rag.search",
                enabled=True,
                config={"top_k": 5, "api_token": "demo-placeholder"},
            )
        )

    response = client.delete(
        f"/admin/tenants/{tenant_id}/plugins/rag.search",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["config"] == {"top_k": 5, "api_token": "[REDACTED]"}


def test_admin_plugin_config_rejects_secret_like_keys(
    client: TestClient,
    admin_session_factory: sessionmaker[Session],
) -> None:
    headers = {"X-Admin-Token": get_settings().admin_token}
    slug = f"tenant-plugin-secret-{uuid4()}"

    created = client.post(
        "/admin/tenants",
        headers=headers,
        json={"slug": slug, "display_name": "Tenant Plugin Secret", "config": {}},
    )
    assert created.status_code == 201
    tenant_id = created.json()["id"]

    response = client.put(
        f"/admin/tenants/{tenant_id}/plugins/rag.search",
        headers=headers,
        json={"config": {"top_k": 5, "api_token": "demo-placeholder"}},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    with admin_session_factory() as session:
        row_count = session.execute(
            text(
                """
                SELECT count(*)
                FROM tenant_plugins
                WHERE tenant_id = :tenant_id AND plugin_name = 'rag.search'
                """
            ),
            {"tenant_id": tenant_id},
        ).scalar_one()

    assert row_count == 0


@pytest.mark.parametrize(
    "credential_key",
    [
        "api-key",  # pragma: allowlist secret
        "authorization",
        "auth_header",
        "private_key",  # pragma: allowlist secret
        "accessKey",
        "to\u200bken",
        "t\u043eken",
    ],
)
def test_admin_plugin_config_rejects_credential_key_bypass_variants(
    client: TestClient,
    admin_session_factory: sessionmaker[Session],
    credential_key: str,
) -> None:
    headers = {"X-Admin-Token": get_settings().admin_token}
    slug = f"tenant-plugin-bypass-{uuid4()}"

    created = client.post(
        "/admin/tenants",
        headers=headers,
        json={"slug": slug, "display_name": "Tenant Plugin Bypass", "config": {}},
    )
    assert created.status_code == 201
    tenant_id = created.json()["id"]

    response = client.put(
        f"/admin/tenants/{tenant_id}/plugins/rag.search",
        headers=headers,
        json={"config": {"top_k": 5, credential_key: "demo-placeholder"}},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    with admin_session_factory() as session:
        row_count = session.execute(
            text(
                """
                SELECT count(*)
                FROM tenant_plugins
                WHERE tenant_id = :tenant_id AND plugin_name = 'rag.search'
                """
            ),
            {"tenant_id": tenant_id},
        ).scalar_one()

    assert row_count == 0


def test_admin_plugin_config_rejects_credential_header_value_smuggling(
    client: TestClient,
    admin_session_factory: sessionmaker[Session],
) -> None:
    headers = {"X-Admin-Token": get_settings().admin_token}
    slug = f"tenant-plugin-header-smuggling-{uuid4()}"

    created = client.post(
        "/admin/tenants",
        headers=headers,
        json={"slug": slug, "display_name": "Tenant Plugin Header Smuggling", "config": {}},
    )
    assert created.status_code == 201
    tenant_id = created.json()["id"]

    response = client.put(
        f"/admin/tenants/{tenant_id}/plugins/rag.search",
        headers=headers,
        json={"config": {"headers": ["Authorization: Bearer demo-placeholder"]}},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    with admin_session_factory() as session:
        row_count = session.execute(
            text(
                """
                SELECT count(*)
                FROM tenant_plugins
                WHERE tenant_id = :tenant_id AND plugin_name = 'rag.search'
                """
            ),
            {"tenant_id": tenant_id},
        ).scalar_one()

    assert row_count == 0


def test_admin_plugin_name_validation_uses_error_envelope(client: TestClient) -> None:
    headers = {"X-Admin-Token": get_settings().admin_token}
    slug = f"tenant-plugin-name-{uuid4()}"

    created = client.post(
        "/admin/tenants",
        headers=headers,
        json={"slug": slug, "display_name": "Tenant Plugin Name", "config": {}},
    )
    assert created.status_code == 201
    tenant_id = created.json()["id"]
    invalid_plugin_name = "x" * 101

    response = client.put(
        f"/admin/tenants/{tenant_id}/plugins/{invalid_plugin_name}",
        headers=headers,
        json={"config": {}},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
