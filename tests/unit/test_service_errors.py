from core.services.errors import ServiceError


def test_service_error_string_uses_public_message() -> None:
    error = ServiceError(code="QUEUE_BACKPRESSURE", message="queue full", status_code=503)

    assert str(error) == "queue full"
