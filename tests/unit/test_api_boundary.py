from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.api.dependencies import require_adapter_principal
from core.api.errors import ApiError, json_safe_details
from core.api.main import create_app
from core.api.routes.admin_tenants import get_tenant_service
from core.config import Settings, get_settings


class EmptyTenantService:
    def list_tenants(self) -> list[object]:
        return []


def create_test_app() -> FastAPI:
    app = create_app()
    app.dependency_overrides[get_tenant_service] = lambda: EmptyTenantService()
    return app


def test_admin_route_rejects_missing_token_with_trace() -> None:
    get_settings.cache_clear()
    client = TestClient(create_test_app())

    response = client.get("/admin/tenants")

    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "UNAUTHORIZED"
    assert UUID(body["error"]["trace_id"])
    assert response.headers["x-trace-id"] == body["error"]["trace_id"]


def test_admin_route_rejects_invalid_token() -> None:
    get_settings.cache_clear()
    client = TestClient(create_test_app())

    response = client.get("/admin/tenants", headers={"X-Admin-Token": "wrong"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_admin_route_preserves_valid_trace_id() -> None:
    get_settings.cache_clear()
    client = TestClient(create_test_app())
    trace_id = "11111111-1111-4111-8111-111111111111"

    response = client.get(
        "/admin/tenants",
        headers={
            "X-Admin-Token": get_settings().admin_token,
            "X-Trace-Id": trace_id,
        },
    )

    assert response.status_code == 200
    assert response.headers["x-trace-id"] == trace_id


def test_error_details_convert_validation_context_to_json_safe_values() -> None:
    details = {
        "errors": [
            {
                "loc": ("body", "config"),
                "ctx": {"error": ValueError("credential-like key")},
            }
        ]
    }

    assert json_safe_details(details) == {
        "errors": [
            {
                "loc": ["body", "config"],
                "ctx": {"error": "credential-like key"},
            }
        ]
    }


def test_settings_reject_default_admin_token_outside_local_env() -> None:
    with pytest.raises(ValueError, match="AGENT_SUPPORT_ADMIN_TOKEN"):
        Settings(environment="production")


def test_settings_reject_default_adapter_token_outside_local_env() -> None:
    with pytest.raises(ValueError, match="AGENT_SUPPORT_ADAPTER_TOKEN"):
        Settings(
            environment="production",
            admin_token="changed-admin-token",
            internal_token="changed-internal-token",
        )


def test_adapter_auth_accepts_valid_local_credential() -> None:
    principal = require_adapter_principal(x_adapter_token=get_settings().adapter_token)

    assert principal.actor_type == "adapter_token"
    assert principal.actor_id == get_settings().adapter_credential_id
    assert principal.platform == "telegram"
    assert principal.external_workspace_id == "sandbox-workspace"


def test_adapter_auth_rejects_missing_credential() -> None:
    with pytest.raises(ApiError) as exc_info:
        require_adapter_principal(x_adapter_token=None)

    assert exc_info.value.code == "UNAUTHORIZED"


def test_internal_ingest_rejects_missing_adapter_credential_with_trace() -> None:
    get_settings.cache_clear()
    client = TestClient(create_app())

    response = client.post(
        "/internal/messages/ingest",
        headers={"X-Trace-Id": "11111111-1111-4111-8111-111111111111"},
        json={
            "trace_id": "11111111-1111-4111-8111-111111111111",
            "platform": "telegram",
            "external_workspace_id": "workspace-a",
            "channel_id": "channel-a",
            "user_id": "user-a",
            "message_id": "message-a",
            "text": "hello",
        },
    )

    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "UNAUTHORIZED"
    assert response.headers["x-trace-id"] == "11111111-1111-4111-8111-111111111111"
