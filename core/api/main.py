from collections.abc import Sequence

import uvicorn
from fastapi import FastAPI

from core.api.routes import health
from core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.service_name, version=settings.service_version)
    app.include_router(health.router)
    return app


app = create_app()


def run(argv: Sequence[str] | None = None) -> None:
    del argv
    uvicorn.run("core.api.main:app", host="0.0.0.0", port=8000, reload=True)
