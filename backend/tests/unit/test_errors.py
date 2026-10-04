"""Unit tests for the AppError hierarchy and envelope helpers (R12.2, §8.2, §14)."""

import json

import pytest

from app.core.errors import (
    AppError,
    ConflictError,
    DatabaseUnavailableError,
    DemoUserNotSeededError,
    DuplicateApplicationError,
    EmailTakenError,
    IngestionSourceUnavailableError,
    InternalError,
    InvalidStatusTransitionError,
    NotFoundError,
    NotReadyError,
    PayloadTooLargeError,
    RequestValidationAppError,
    ResumeEmptyError,
    UnknownDemoUserError,
    UpstreamUnavailableError,
    error_envelope,
    error_response,
    sanitize_validation_errors,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("error_class", "status_code", "code"),
    [
        (NotFoundError, 404, "NOT_FOUND"),
        (RequestValidationAppError, 422, "VALIDATION_ERROR"),
        (DuplicateApplicationError, 409, "DUPLICATE_APPLICATION"),
        (InvalidStatusTransitionError, 409, "INVALID_STATUS_TRANSITION"),
        (EmailTakenError, 409, "EMAIL_TAKEN"),
        (ConflictError, 409, "CONFLICT"),
        (ResumeEmptyError, 422, "RESUME_EMPTY"),
        (IngestionSourceUnavailableError, 502, "INGESTION_SOURCE_UNAVAILABLE"),
        (PayloadTooLargeError, 413, "PAYLOAD_TOO_LARGE"),
        (UnknownDemoUserError, 401, "UNKNOWN_DEMO_USER"),
        (DemoUserNotSeededError, 503, "DEMO_USER_NOT_SEEDED"),
        (DatabaseUnavailableError, 503, "DATABASE_UNAVAILABLE"),
        (InternalError, 500, "INTERNAL_ERROR"),
    ],
)
def test_app_error_subclass_default_has_status_and_code(
    error_class: type[AppError], status_code: int, code: str
) -> None:
    error = error_class()

    assert isinstance(error, AppError)
    assert error.status_code == status_code
    assert error.code == code
    assert error.message
    assert error.details is None


@pytest.mark.parametrize(
    ("child", "parent"),
    [
        (DuplicateApplicationError, ConflictError),
        (InvalidStatusTransitionError, ConflictError),
        (EmailTakenError, ConflictError),
        (ResumeEmptyError, RequestValidationAppError),
        (IngestionSourceUnavailableError, UpstreamUnavailableError),
        (DemoUserNotSeededError, NotReadyError),
        (DatabaseUnavailableError, NotReadyError),
    ],
)
def test_app_error_subclass_inherits_design_parent(
    child: type[AppError], parent: type[AppError]
) -> None:
    assert issubclass(child, parent)


def test_app_error_custom_message_and_details_kept() -> None:
    details: dict[str, object] = {"from": "Offer", "to": "Applied", "allowed": ["Withdrawn"]}

    error = InvalidStatusTransitionError("Cannot move from Offer to Applied", details=details)

    assert error.message == "Cannot move from Offer to Applied"
    assert str(error) == "Cannot move from Offer to Applied"
    assert error.details == details


def test_app_error_explicit_code_and_status_override_defaults() -> None:
    error = AppError("Teapot", code="TEAPOT", status_code=418)

    assert (error.code, error.status_code, error.message) == ("TEAPOT", 418, "Teapot")


def test_error_envelope_called_returns_standard_shape() -> None:
    envelope = error_envelope("NOT_FOUND", "Job 5 not found", {"job_id": 5})

    assert envelope == {
        "error": {"code": "NOT_FOUND", "message": "Job 5 not found", "details": {"job_id": 5}}
    }


def test_error_envelope_without_details_has_null_details() -> None:
    assert error_envelope("X", "y") == {"error": {"code": "X", "message": "y", "details": None}}


def test_error_response_called_returns_json_with_status() -> None:
    response = error_response(409, "CONFLICT", "Conflict.", headers={"X-Test": "1"})

    assert response.status_code == 409
    assert response.headers["X-Test"] == "1"
    assert json.loads(bytes(response.body)) == error_envelope("CONFLICT", "Conflict.")


def test_sanitize_validation_errors_strips_input_ctx_and_url() -> None:
    raw: list[dict[str, object]] = [
        {
            "type": "int_parsing",
            "loc": ("body", "age"),
            "msg": "Input should be a valid integer",
            "input": "secret-value",
            "ctx": {"error": "secret-value"},
            "url": "https://errors.pydantic.dev",
        }
    ]

    assert sanitize_validation_errors(raw) == [
        {"loc": ["body", "age"], "msg": "Input should be a valid integer", "type": "int_parsing"}
    ]
