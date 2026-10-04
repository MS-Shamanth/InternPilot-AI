"""Application errors, the error envelope and FastAPI exception handlers (R12.2, R12.3, §8.2, §14).

Every failed request is answered with `{"error": {"code", "message", "details"}}`. Services raise
`AppError` subclasses; framework and database exceptions are translated here. Responses never
carry stack traces, SQL, raw user input or configuration values.
"""

import logging
from collections.abc import Mapping, Sequence
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)

type ErrorDetails = dict[str, object] | list[dict[str, object]] | None
type ErrorEnvelope = dict[str, dict[str, object]]

INTERNAL_ERROR_CODE = "INTERNAL_ERROR"
INTERNAL_ERROR_MESSAGE = "An unexpected error occurred."
VALIDATION_ERROR_CODE = "VALIDATION_ERROR"
VALIDATION_ERROR_MESSAGE = "Request validation failed."
CONFLICT_CODE = "CONFLICT"
CONFLICT_MESSAGE = "The request conflicts with existing data."
DATABASE_UNAVAILABLE_CODE = "DATABASE_UNAVAILABLE"
DATABASE_UNAVAILABLE_MESSAGE = "The database is unavailable. Please retry shortly."
HTTP_ERROR_CODE = "HTTP_ERROR"

HTTP_STATUS_CODES: dict[int, str] = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: CONFLICT_CODE,
    413: "PAYLOAD_TOO_LARGE",
    415: "UNSUPPORTED_MEDIA_TYPE",
    422: VALIDATION_ERROR_CODE,
}


class AppError(Exception):
    """Base for errors raised by services; carries everything needed for the envelope.

    Subclasses set `default_code`, `default_status_code` and `default_message`; callers may
    override the message and attach structured, non-sensitive `details`.
    """

    default_code: str = INTERNAL_ERROR_CODE
    default_status_code: int = 500
    default_message: str = INTERNAL_ERROR_MESSAGE

    def __init__(
        self,
        message: str | None = None,
        *,
        details: ErrorDetails = None,
        code: str | None = None,
        status_code: int | None = None,
    ) -> None:
        self.code = code or self.default_code
        self.message = message or self.default_message
        self.status_code = status_code or self.default_status_code
        self.details = details
        super().__init__(self.message)


class InternalError(AppError):
    """500 `INTERNAL_ERROR`; the response always uses the generic message."""


class SeedDataError(InternalError):
    """A seed file is missing, unreadable or invalid (design.md §12). Raised only by the seed
    command, which logs `message` and exits 1; it never reaches an HTTP response."""

    default_message = "Seed data is invalid."


class NotFoundError(AppError):
    default_code = "NOT_FOUND"
    default_status_code = 404
    default_message = "The requested resource was not found."


class ConflictError(AppError):
    default_code = CONFLICT_CODE
    default_status_code = 409
    default_message = CONFLICT_MESSAGE


class DuplicateApplicationError(ConflictError):
    default_code = "DUPLICATE_APPLICATION"
    default_message = "An application for this job already exists."


class InvalidStatusTransitionError(ConflictError):
    default_code = "INVALID_STATUS_TRANSITION"
    default_message = "This status change is not allowed."


class EmailTakenError(ConflictError):
    default_code = "EMAIL_TAKEN"
    default_message = "This email is already used by another user."


class RequestValidationAppError(AppError):
    default_code = VALIDATION_ERROR_CODE
    default_status_code = 422
    default_message = VALIDATION_ERROR_MESSAGE


class ResumeEmptyError(RequestValidationAppError):
    default_code = "RESUME_EMPTY"
    default_message = "No resume text was provided and the profile has no stored resume."


class PayloadTooLargeError(AppError):
    default_code = "PAYLOAD_TOO_LARGE"
    default_status_code = 413
    default_message = "Request payload is too large."


class UpstreamUnavailableError(AppError):
    """502; the only upstream the API reports on is job ingestion (LLM failures degrade)."""

    default_code = "UPSTREAM_UNAVAILABLE"
    default_status_code = 502
    default_message = "An upstream service is unavailable."


class IngestionSourceUnavailableError(UpstreamUnavailableError):
    default_code = "INGESTION_SOURCE_UNAVAILABLE"
    default_message = "The job source is unavailable and no fallback was used."


class UnknownDemoUserError(AppError):
    default_code = "UNKNOWN_DEMO_USER"
    default_status_code = 401
    default_message = "The requested demo user does not exist."


class NotReadyError(AppError):
    default_code = "NOT_READY"
    default_status_code = 503
    default_message = "The service is not ready."


class DemoUserNotSeededError(NotReadyError):
    default_code = "DEMO_USER_NOT_SEEDED"
    default_message = "The demo user has not been seeded yet."


class DatabaseUnavailableError(NotReadyError):
    default_code = DATABASE_UNAVAILABLE_CODE
    default_message = DATABASE_UNAVAILABLE_MESSAGE


def error_envelope(code: str, message: str, details: ErrorDetails = None) -> ErrorEnvelope:
    """Build the standard `{"error": {"code", "message", "details"}}` body."""
    return {"error": {"code": code, "message": message, "details": details}}


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: ErrorDetails = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Return the envelope as a JSON response with the given status."""
    return JSONResponse(
        status_code=status_code,
        content=error_envelope(code, message, details),
        headers=headers,
    )


def _internal_error_response() -> JSONResponse:
    return error_response(500, INTERNAL_ERROR_CODE, INTERNAL_ERROR_MESSAGE)


def sanitize_validation_errors(errors: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    """Keep only `loc`, `msg`, `type`; drops `input`, `ctx` and `url` so input is never echoed."""
    sanitized: list[dict[str, object]] = []
    for error in errors:
        loc = error.get("loc", ())
        sanitized.append(
            {
                "loc": list(loc) if isinstance(loc, tuple | list) else [loc],
                "msg": error.get("msg", ""),
                "type": error.get("type", ""),
            }
        )
    return sanitized


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    if exc.status_code >= 500 and exc.code == INTERNAL_ERROR_CODE:
        logger.error("Internal error on %s %s", request.method, request.url.path, exc_info=exc)
        return _internal_error_response()
    logger.debug("AppError %s (%d) on %s", exc.code, exc.status_code, request.url.path)
    return error_response(exc.status_code, exc.code, exc.message, exc.details)


async def request_validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    logger.debug("Validation failed on %s %s", request.method, request.url.path)
    details = sanitize_validation_errors(list(exc.errors()))
    return error_response(422, VALIDATION_ERROR_CODE, VALIDATION_ERROR_MESSAGE, details)


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Map framework HTTP errors (unknown route, wrong method, bad body) to the envelope.

    The message is the standard status phrase rather than `exc.detail`, so nothing raised by
    framework internals is echoed back.
    """
    if exc.status_code >= 500:
        logger.error("HTTP %d raised on %s", exc.status_code, request.url.path)
        return _internal_error_response()
    code = HTTP_STATUS_CODES.get(exc.status_code, HTTP_ERROR_CODE)
    try:
        message = f"{HTTPStatus(exc.status_code).phrase}."
    except ValueError:
        message = "The request could not be processed."
    return error_response(exc.status_code, code, message, headers=exc.headers)


async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    # Only the DBAPI exception type is logged: the message may contain SQL and bound values.
    logger.warning("Integrity error on %s: %s", request.url.path, type(exc.orig).__name__)
    return error_response(409, CONFLICT_CODE, CONFLICT_MESSAGE)


async def operational_error_handler(request: Request, exc: OperationalError) -> JSONResponse:
    logger.error("Database unavailable on %s: %s", request.url.path, type(exc.orig).__name__)
    return error_response(503, DATABASE_UNAVAILABLE_CODE, DATABASE_UNAVAILABLE_MESSAGE)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Last resort: log the traceback (request id via the logging filter), reply generically."""
    logger.error("Unhandled exception on %s %s", request.method, request.url.path, exc_info=exc)
    return _internal_error_response()


def register_exception_handlers(app: FastAPI) -> None:
    """Install every handler; `Exception` is served by Starlette's `ServerErrorMiddleware`."""
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(IntegrityError, integrity_error_handler)
    app.add_exception_handler(OperationalError, operational_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
