"""Errors as RFC 9457 problem details. Internal details never reach the client."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from fieldshift.application.errors import (
    ApplicationError,
    ClimateDataUnavailableError,
    ClimateProviderRateLimitedError,
)

logger = logging.getLogger(__name__)
PROBLEM_JSON = "application/problem+json"


def problem(
    status: int, code: str, detail: str, extra: dict[str, object] | None = None
) -> JSONResponse:
    body: dict[str, object] = {
        "type": "about:blank",
        "status": status,
        "code": code,
        "detail": detail,
    }
    body.update(extra or {})
    headers = {"Retry-After": "60"} if code == ClimateProviderRateLimitedError.code else None
    return JSONResponse(body, status_code=status, media_type=PROBLEM_JSON, headers=headers)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation(_: Request, error: RequestValidationError) -> JSONResponse:
        errors = [
            {
                "loc": list(e.get("loc", ())),
                "msg": str(e.get("msg", "")),
                "type": str(e.get("type", "")),
            }
            for e in error.errors()
        ]
        return problem(
            422,
            "validation_error",
            "La requête contient des valeurs invalides.",
            {"errors": errors},
        )

    @app.exception_handler(ApplicationError)
    async def application(_: Request, error: ApplicationError) -> JSONResponse:
        status = 503 if isinstance(error, ClimateDataUnavailableError) else 422
        return problem(status, error.code, error.message_fr)

    @app.exception_handler(HTTPException)
    async def http(_: Request, error: HTTPException) -> JSONResponse:
        return problem(error.status_code, "http_error", str(error.detail))

    @app.exception_handler(Exception)
    async def internal(request: Request, error: Exception) -> JSONResponse:
        logger.exception("unhandled error", extra={"path": request.url.path})
        return problem(500, "internal_error", "Erreur interne. Réessayez ou contactez l'équipe.")
