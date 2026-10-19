"""Uniform error body and handlers (rule X-3). Errors are logged once, here (rule O-3).

{"error": {"code": "AUTH_ACCOUNT_LOCKED", "message": "...", "details": {}, "request_id": "..."}}
"""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from platform_core.errors import (
    AppError,
    ConflictError,
    DependencyTimeoutError,
    ForbiddenError,
    InvalidInputError,
    NotFoundError,
    RateLimitedError,
    UnauthenticatedError,
    UnavailableError,
)
from platform_observability import get_logger, get_request_id

_log = get_logger("http.errors")

# Most specific first (DependencyTimeoutError subclasses UnavailableError).
_STATUS_BY_CATEGORY: tuple[tuple[type[AppError], int], ...] = (
    (InvalidInputError, 422),
    (UnauthenticatedError, 401),
    (ForbiddenError, 403),
    (NotFoundError, 404),
    (ConflictError, 409),
    (RateLimitedError, 429),
    (DependencyTimeoutError, 504),
    (UnavailableError, 503),
)


def status_for(exc: AppError) -> int:
    for category, status in _STATUS_BY_CATEGORY:
        if isinstance(exc, category):
            return status
    return 500


def error_body(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "request_id": get_request_id(),
        }
    }


async def _app_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    status = status_for(exc)
    headers: dict[str, str] = {}
    if isinstance(exc, RateLimitedError) and exc.retry_after_seconds is not None:
        headers["Retry-After"] = str(exc.retry_after_seconds)
    if status >= 500:
        _log.error("request_failed", error_code=exc.code, status=status, exc_info=exc)
    else:
        _log.info("request_rejected", error_code=exc.code, status=status)
    return JSONResponse(
        error_body(exc.code, exc.message, exc.details), status_code=status, headers=headers
    )


async def _validation_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    fields = [
        {"loc": [str(p) for p in err["loc"]], "type": err["type"], "msg": err["msg"]}
        for err in exc.errors()
    ]
    return JSONResponse(
        error_body("INVALID_INPUT", "The request is invalid.", {"fields": fields}), status_code=422
    )


async def _http_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    code = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}.get(exc.status_code, "HTTP_ERROR")
    return JSONResponse(
        error_body(code, str(exc.detail)), status_code=exc.status_code, headers=exc.headers
    )


async def _unhandled_handler(_: Request, exc: Exception) -> JSONResponse:
    _log.error("unhandled_exception", exc_info=exc)
    return JSONResponse(
        error_body("INTERNAL_ERROR", "An unexpected error occurred."), status_code=500
    )


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_handler)
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(Exception, _unhandled_handler)
