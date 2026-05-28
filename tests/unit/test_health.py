from fastapi.testclient import TestClient

from core.api.main import create_app


def test_healthz_returns_service_status() -> None:
    client = TestClient(create_app())

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "Agent Support",
        "version": "0.1.0",
    }
