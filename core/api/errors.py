from collections.abc import Mapping
from typing import Any
from uuid import UUID

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from core.services.errors import ServiceError


class ErrorBody(BaseModel):
    code: str
    message: str
    trace_id: str
    details: dict[str, Any]


class ErrorResponse(BaseModel):
    error: ErrorBody


class ApiError(Exception):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        status_code: int,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


def request_trace_id(request: Request) -> str:
    trace_id = getattr(request.state, "trace_id", None)
    if isinstance(trace_id, UUID):
        return str(trace_id)
    return str(trace_id or "")


def json_safe_value(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): json_safe_value(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [json_safe_value(item) for item in value]
    return str(value)


def json_safe_details(details: dict[str, Any] | None) -> dict[str, Any]:
    if details is None:
        return {}
    safe_value = json_safe_value(details)
    return safe_value if isinstance(safe_value, dict) else {}


def error_response(
    *,
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    trace_id = request_trace_id(request)
    response = ErrorResponse(
        error=ErrorBody(
            code=code,
            message=message,
            trace_id=trace_id,
            details=json_safe_details(details),
        )
    )
    return JSONResponse(
        status_code=status_code,
        content=response.model_dump(mode="json"),
        headers={"X-Trace-Id": trace_id} if trace_id else None,
    )


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return error_response(
        request=request,
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        details=exc.details,
    )


async def service_error_handler(request: Request, exc: ServiceError) -> JSONResponse:
    return error_response(
        request=request,
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return error_response(
        request=request,
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        code="VALIDATION_ERROR",
        message="Request validation failed",
        details={"errors": exc.errors()},
    )
