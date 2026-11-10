"""FastAPI application factory. Run with: uvicorn --factory fieldshift.api.app:create_app"""

from __future__ import annotations

import logging
import re
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import date

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from fieldshift import __version__
from fieldshift.api.dependencies import build_container
from fieldshift.api.errors import install_error_handlers
from fieldshift.api.routes import analysis, catalog
from fieldshift.application.ports import HistoricalClimateProvider
from fieldshift.infrastructure.logging import configure_logging
from fieldshift.infrastructure.settings import Settings

logger = logging.getLogger("fieldshift.access")
_REQUEST_ID = re.compile(r"^[A-Za-z0-9-]{1,64}$")


async def request_context(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    incoming = request.headers.get("X-Request-ID", "")
    request_id = incoming if _REQUEST_ID.match(incoming) else uuid.uuid4().hex
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": round((time.perf_counter() - started) * 1000, 1),
        },
    )
    return response


def create_app(
    settings: Settings | None = None,
    *,
    provider: HistoricalClimateProvider | None = None,
    today: Callable[[], date] | None = None,
) -> FastAPI:
    settings = settings or Settings()
    configure_logging(settings.log_level, settings.log_format)
    container = build_container(settings, provider=provider, today=today)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        if container.http_client is not None:
            container.http_client.close()

    app = FastAPI(
        title="Field Shift API",
        version=__version__,
        description="Comparaison de rotations de cultures face au climat historique (NASA POWER).",
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.state.container = container
    app.middleware("http")(request_context)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    install_error_handlers(app)
    app.include_router(catalog.router, prefix="/api/v1")
    app.include_router(analysis.router, prefix="/api/v1")
    return app
