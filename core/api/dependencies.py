from collections.abc import Iterator
from secrets import compare_digest
from uuid import UUID, uuid4

from fastapi import Header, Request, status
from sqlalchemy.orm import Session

from core.api.errors import ApiError
from core.config import get_settings
from core.persistence.db import admin_session_scope
from core.services.principals import AdapterPrincipal, AdminPrincipal


def parse_trace_id(raw_trace_id: str | None) -> UUID:
    if raw_trace_id is None or raw_trace_id == "":
        return uuid4()
    try:
        return UUID(raw_trace_id)
    except ValueError:
        return uuid4()


def get_trace_id(request: Request) -> UUID:
    trace_id = getattr(request.state, "trace_id", None)
    if isinstance(trace_id, UUID):
        return trace_id
    trace_id = parse_trace_id(None)
    request.state.trace_id = trace_id
    return trace_id


def require_admin_principal(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> AdminPrincipal:
    expected_token = get_settings().admin_token
    if x_admin_token is None or not compare_digest(x_admin_token, expected_token):
        raise ApiError(
            code="UNAUTHORIZED",
            message="Missing or invalid admin token",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    return AdminPrincipal(actor_type="admin_token", actor_id="local-admin")


def require_internal_token(
    x_internal_token: str | None = Header(default=None, alias="X-Internal-Token"),
) -> None:
    expected_token = get_settings().internal_token
    if x_internal_token is None or not compare_digest(x_internal_token, expected_token):
        raise ApiError(
            code="UNAUTHORIZED",
            message="Missing or invalid internal token",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


def require_adapter_principal(
    x_adapter_token: str | None = Header(default=None, alias="X-Adapter-Token"),
) -> AdapterPrincipal:
    settings = get_settings()
    if x_adapter_token is None or not compare_digest(x_adapter_token, settings.adapter_token):
        raise ApiError(
            code="UNAUTHORIZED",
            message="Missing or invalid adapter credential",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    return AdapterPrincipal(
        actor_type="adapter_token",
        actor_id=settings.adapter_credential_id,
        platform=settings.adapter_platform,
        external_workspace_id=settings.adapter_external_workspace_id,
        external_channel_id=settings.adapter_external_channel_id,
    )


def get_admin_session() -> Iterator[Session]:
    with admin_session_scope() as session:
        yield session
