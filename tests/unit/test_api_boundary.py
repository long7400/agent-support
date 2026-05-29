from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.api.errors import json_safe_details
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
