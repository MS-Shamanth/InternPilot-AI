"""API tests for the exception handlers registered by `create_app` (R12.2, R12.3, R12.5, §8.2)."""

import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import IntegrityError, OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import InternalError, InvalidStatusTransitionError, NotFoundError
from app.core.logging import RequestIdFilter
from app.main import create_app

pytestmark = pytest.mark.api

SENSITIVE_INPUT = "fake-sensitive-input-0123456789"
LEAKY_MESSAGE = "boom: password=hunter2 at /srv/app/secret.py"
SQL_TEXT = "INSERT INTO users (email) VALUES (%(email)s)"


class EchoBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    age: int


def _build_app() -> FastAPI:
    app = create_app()

    @app.get("/test/not-found")
    def raise_not_found() -> None:
        raise NotFoundError("Job 42 not found", details={"job_id": 42})

    @app.get("/test/transition")
    def raise_transition() -> None:
        raise InvalidStatusTransitionError(
            "Cannot move from Offer to Applied",
            details={"from": "Offer", "to": "Applied", "allowed": ["Withdrawn"]},
        )

    @app.post("/test/echo")
    def echo(body: EchoBody) -> dict[str, int]:
        return {"age": body.age}

    @app.get("/test/items/{item_id}")
    def read_item(item_id: int) -> dict[str, int]:
        return {"item_id": item_id}

    @app.get("/test/crash")
    def crash() -> None:
        raise RuntimeError(LEAKY_MESSAGE)

    @app.get("/test/db-down")
    def db_down() -> None:
        raise OperationalError(
            SQL_TEXT, {"email": SENSITIVE_INPUT}, Exception("connection refused")
        )

    @app.get("/test/db-conflict")
    def db_conflict() -> None:
        raise IntegrityError(SQL_TEXT, {"email": SENSITIVE_INPUT}, Exception("unique violation"))

    @app.get("/test/internal")
    def raise_internal() -> None:
        raise InternalError(LEAKY_MESSAGE, details={"path": "/srv/app/secret.py"})

    @app.get("/test/http-500")
    def raise_http_500() -> None:
        raise StarletteHTTPException(status_code=500, detail=LEAKY_MESSAGE)

    @app.get("/test/http-nonstandard")
    def raise_http_nonstandard() -> None:
        raise StarletteHTTPException(status_code=499, detail=LEAKY_MESSAGE)

    return app


@pytest.fixture
def client() -> TestClient:
    return TestClient(_build_app(), raise_server_exceptions=False)


def test_app_error_raised_returns_status_and_envelope(client: TestClient) -> None:
    response = client.get("/test/not-found")

    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "NOT_FOUND", "message": "Job 42 not found", "details": {"job_id": 42}}
    }
    assert response.headers["X-Request-ID"]


def test_invalid_transition_raised_returns_409_with_allowed(client: TestClient) -> None:
    response = client.get("/test/transition")

    assert response.status_code == 409
    assert response.json()["error"] == {
        "code": "INVALID_STATUS_TRANSITION",
        "message": "Cannot move from Offer to Applied",
        "details": {"from": "Offer", "to": "Applied", "allowed": ["Withdrawn"]},
    }


def test_body_validation_failed_returns_422_without_echoing_input(client: TestClient) -> None:
    response = client.post("/test/echo", json={"age": SENSITIVE_INPUT, "extra": SENSITIVE_INPUT})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["message"] == "Request validation failed."
    assert {tuple(item["loc"]) for item in error["details"]} == {
        ("body", "age"),
        ("body", "extra"),
    }
    assert all(set(item) == {"loc", "msg", "type"} for item in error["details"])
    assert SENSITIVE_INPUT not in response.text


def test_path_param_invalid_returns_422_envelope(client: TestClient) -> None:
    response = client.get(f"/test/items/{SENSITIVE_INPUT}")

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["loc"] == ["path", "item_id"]
    assert SENSITIVE_INPUT not in response.text


def test_unknown_route_returns_404_envelope(client: TestClient) -> None:
    response = client.get("/api/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "NOT_FOUND", "message": "Not Found.", "details": None}
    }
    assert response.headers["X-Request-ID"]


def test_wrong_method_returns_405_envelope_with_allow_header(client: TestClient) -> None:
    response = client.delete("/test/not-found")

    assert response.status_code == 405
    assert response.json()["error"]["code"] == "METHOD_NOT_ALLOWED"
    assert "GET" in response.headers["allow"]


def test_unhandled_exception_returns_generic_500(client: TestClient) -> None:
    response = client.get("/test/crash", headers={"X-Request-ID": "req-500"})

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "An unexpected error occurred.",
            "details": None,
        }
    }
    assert "hunter2" not in response.text
    assert "Traceback" not in response.text
    assert "RuntimeError" not in response.text
    assert response.headers["X-Request-ID"] == "req-500"


def test_unhandled_exception_logged_at_error_with_request_id(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.handler.addFilter(RequestIdFilter())

    with caplog.at_level(logging.ERROR, logger="app.core.errors"):
        client.get("/test/crash", headers={"X-Request-ID": "req-log-1"})

    records = [r for r in caplog.records if r.name == "app.core.errors"]
    assert len(records) == 1
    assert records[0].levelno == logging.ERROR
    assert records[0].exc_info is not None
    assert records[0].request_id == "req-log-1"


def test_operational_error_returns_503_database_unavailable(client: TestClient) -> None:
    response = client.get("/test/db-down")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATABASE_UNAVAILABLE"
    assert "INSERT" not in response.text
    assert SENSITIVE_INPUT not in response.text


def test_integrity_error_returns_409_conflict_without_sql(client: TestClient) -> None:
    response = client.get("/test/db-conflict")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"
    assert "INSERT" not in response.text
    assert SENSITIVE_INPUT not in response.text


GENERIC_500 = {
    "error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred.", "details": None}
}


def test_internal_app_error_returns_generic_500_without_details(client: TestClient) -> None:
    response = client.get("/test/internal")

    assert response.status_code == 500
    assert response.json() == GENERIC_500
    assert "secret.py" not in response.text


def test_framework_http_500_returns_generic_500_without_detail(client: TestClient) -> None:
    response = client.get("/test/http-500")

    assert response.status_code == 500
    assert response.json() == GENERIC_500


def test_nonstandard_http_status_returns_envelope_with_generic_message(
    client: TestClient,
) -> None:
    response = client.get("/test/http-nonstandard")

    assert response.status_code == 499
    error = response.json()["error"]
    assert error["message"] == "The request could not be processed."
    assert "hunter2" not in response.text
