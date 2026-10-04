"""API tests for CORS (security.md "CORS and headers", R12.5, design.md §13.1, §14)."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import DEFAULT_CORS_ORIGINS, Settings
from app.main import create_app

pytestmark = pytest.mark.api

ALLOWED_ORIGIN = DEFAULT_CORS_ORIGINS[0]
DISALLOWED_ORIGIN = "https://evil.example.com"
ALLOW_ORIGIN = "access-control-allow-origin"


def _preflight(client: TestClient, origin: str, method: str = "PATCH") -> dict[str, str]:
    response = client.options(
        "/api/health",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": "content-type,x-demo-user",
        },
    )
    return {"status": str(response.status_code), **response.headers}


def test_cors_preflight_allowed_origin_returns_allowed_methods_and_headers(
    client: TestClient,
) -> None:
    headers = _preflight(client, ALLOWED_ORIGIN)

    assert headers["status"] == "200"
    assert headers[ALLOW_ORIGIN] == ALLOWED_ORIGIN
    allowed_methods = {
        method.strip() for method in headers["access-control-allow-methods"].split(",")
    }
    assert allowed_methods == {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"}
    allowed_headers = headers["access-control-allow-headers"].lower()
    for header in ("content-type", "accept", "x-demo-user", "x-request-id"):
        assert header in allowed_headers
    assert "access-control-allow-credentials" not in headers
    assert headers["x-request-id"]


def test_cors_preflight_disallowed_origin_has_no_allow_origin(client: TestClient) -> None:
    headers = _preflight(client, DISALLOWED_ORIGIN)

    assert headers["status"] == "400"
    assert ALLOW_ORIGIN not in headers


def test_cors_simple_get_disallowed_origin_has_no_allow_origin(client: TestClient) -> None:
    response = client.get("/api/health", headers={"Origin": DISALLOWED_ORIGIN})

    assert response.status_code == 200
    assert ALLOW_ORIGIN not in response.headers


def test_cors_simple_get_allowed_origin_exposes_request_id(client: TestClient) -> None:
    response = client.get("/api/health", headers={"Origin": ALLOWED_ORIGIN})

    assert response.status_code == 200
    assert response.headers[ALLOW_ORIGIN] == ALLOWED_ORIGIN
    assert response.headers["access-control-expose-headers"] == "X-Request-ID"
    assert response.headers["x-request-id"]
    assert "access-control-allow-credentials" not in response.headers


def test_cors_never_answers_with_wildcard(client: TestClient) -> None:
    for origin in (ALLOWED_ORIGIN, DISALLOWED_ORIGIN, "null"):
        response = client.get("/api/health", headers={"Origin": origin})
        assert response.headers.get(ALLOW_ORIGIN) != "*"
        preflight = _preflight(client, origin, method="GET")
        assert preflight.get(ALLOW_ORIGIN) != "*"


def test_cors_payload_too_large_keeps_cors_and_request_id(client: TestClient) -> None:
    response = client.put(
        "/api/profile",
        content=b"x" * 5_000_001,
        headers={"Origin": ALLOWED_ORIGIN, "Content-Type": "application/json"},
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"
    assert response.headers[ALLOW_ORIGIN] == ALLOWED_ORIGIN
    assert response.headers["x-request-id"]


def test_cors_unhandled_500_keeps_cors_and_request_id() -> None:
    app: FastAPI = create_app()

    @app.get("/test/crash")
    def crash() -> None:
        raise RuntimeError("boom")

    with TestClient(app, raise_server_exceptions=False) as test_client:
        response = test_client.get("/test/crash", headers={"Origin": ALLOWED_ORIGIN})

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert response.headers[ALLOW_ORIGIN] == ALLOWED_ORIGIN
    assert response.headers["x-request-id"]


def test_cors_origins_come_from_settings() -> None:
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        cors_origins=["https://app.example.com"],
    )
    with TestClient(create_app(settings)) as test_client:
        allowed = test_client.get("/api/health", headers={"Origin": "https://app.example.com"})
        default = test_client.get("/api/health", headers={"Origin": ALLOWED_ORIGIN})

    assert allowed.headers[ALLOW_ORIGIN] == "https://app.example.com"
    assert ALLOW_ORIGIN not in default.headers
