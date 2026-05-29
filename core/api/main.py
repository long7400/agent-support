from collections.abc import Awaitable, Callable, Sequence
from typing import Any, cast

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.responses import Response

from core.api.dependencies import parse_trace_id
from core.api.errors import (
    ApiError,
    api_error_handler,
    service_error_handler,
    validation_error_handler,
)
from core.api.routes import admin_audit, admin_plugins, admin_tenants, health
from core.config import get_settings
from core.services.errors import ServiceError


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.service_name, version=settings.service_version)
    app.add_exception_handler(ApiError, cast(Any, api_error_handler))
    app.add_exception_handler(ServiceError, cast(Any, service_error_handler))
    app.add_exception_handler(RequestValidationError, cast(Any, validation_error_handler))

    @app.middleware("http")
    async def trace_id_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        trace_id = parse_trace_id(request.headers.get("X-Trace-Id"))
        request.state.trace_id = trace_id
        response = await call_next(request)
        response.headers["X-Trace-Id"] = str(trace_id)
        return response

    app.include_router(health.router)
    app.include_router(admin_tenants.router)
    app.include_router(admin_plugins.router)
    app.include_router(admin_audit.router)
    return app


app = create_app()


def run(argv: Sequence[str] | None = None) -> None:
    del argv
    uvicorn.run("core.api.main:app", host="0.0.0.0", port=8000, reload=True)
