"""One error model for every response (AD-8)."""

from __future__ import annotations

import logging
import traceback
from collections.abc import Sequence
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from ..domain.errors import NotFoundError, ReturnDeniedError, ServiceUnavailableError
from .schemas import ErrorResponse

logger = logging.getLogger(__name__)

ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorResponse, "description": "Not found"},
    422: {"model": ErrorResponse, "description": "Invalid request or denied return"},
    500: {"model": ErrorResponse, "description": "Internal error"},
    503: {"model": ErrorResponse, "description": "Service unhealthy"},
}

_HTTP_CODES = {404: ("NOT_FOUND", "Not found"), 405: ("METHOD_NOT_ALLOWED", "Method not allowed")}


def error_response(
    status_code: int, code: str, message: str, headers: dict[str, str] | None = None
) -> JSONResponse:
    body = ErrorResponse.model_validate({"error": {"code": code, "message": message}})
    return JSONResponse(status_code=status_code, content=body.model_dump(), headers=headers)


def validation_message(errors: Sequence[Any]) -> str:
    """Build the message from ``loc`` and ``type`` only, never from ``input``."""
    parts = []
    for err in errors:
        loc = ".".join(str(p) for p in err.get("loc", ()))
        parts.append(f"{loc}: {err.get('type', 'invalid')}")
    return "; ".join(parts) or "Invalid request"


async def _not_found(_: Request, exc: NotFoundError) -> JSONResponse:
    return error_response(404, "NOT_FOUND", exc.message)


async def _return_denied(_: Request, exc: ReturnDeniedError) -> JSONResponse:
    return error_response(422, exc.reason.value, exc.message)


async def _unavailable(_: Request, exc: ServiceUnavailableError) -> JSONResponse:
    return error_response(503, "UNHEALTHY", exc.message)


async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
    return error_response(422, "INVALID_REQUEST", validation_message(exc.errors()))


async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    code, message = _HTTP_CODES.get(exc.status_code, (f"HTTP_{exc.status_code}", "HTTP error"))
    return error_response(exc.status_code, code, message, headers=exc.headers)


def log_unexpected(exc: BaseException) -> None:
    """Log the type and stack frames, never ``str(exc)``: it may hold request data (AD-7)."""
    frames = "".join(traceback.format_tb(exc.__traceback__))
    logger.error(
        "unhandled error: %s\nTraceback (message removed):\n%s", type(exc).__name__, frames
    )


def internal_error_response() -> JSONResponse:
    return error_response(500, "INTERNAL_ERROR", "Internal server error")


class UnexpectedErrorMiddleware:
    """Turn unhandled exceptions into the AD-8 500 without re-raising.

    Starlette's ServerErrorMiddleware re-raises after running an ``Exception``
    handler, and uvicorn then logs the full traceback including the exception
    message. Catching here, inside ServerErrorMiddleware, stops that.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def send_tracking(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, send_tracking)
        except Exception as exc:
            log_unexpected(exc)
            if not started:  # once headers are sent, the response cannot change
                await internal_error_response()(scope, receive, send)


async def _unexpected(_: Request, exc: Exception) -> JSONResponse:
    """Backstop for errors raised outside UnexpectedErrorMiddleware."""
    log_unexpected(exc)
    return internal_error_response()


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(NotFoundError, _not_found)
    app.add_exception_handler(ReturnDeniedError, _return_denied)
    app.add_exception_handler(ServiceUnavailableError, _unavailable)
    app.add_exception_handler(RequestValidationError, _validation)
    app.add_exception_handler(StarletteHTTPException, _http)
    app.add_exception_handler(Exception, _unexpected)
    app.add_middleware(UnexpectedErrorMiddleware)
