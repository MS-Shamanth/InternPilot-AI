"""Tests for RequestIdMiddleware and BodySizeLimitMiddleware (R12.5, design.md §8.1, §14)."""

import re
from collections.abc import Iterator

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from pydantic import BaseModel
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from app.core.logging import get_request_id
from app.core.middleware import (
    MAX_REQUEST_BODY_BYTES,
    BodySizeLimitMiddleware,
    RequestIdMiddleware,
    resolve_request_id,
)
from app.main import create_app

UUID_HEX = re.compile(r"[0-9a-f]{32}")
SMALL_LIMIT = 100


class EchoBody(BaseModel):
    text: str


async def _echo_request_id(request: Request) -> JSONResponse:
    return JSONResponse({"request_id": get_request_id()})


async def _body_length(request: Request) -> JSONResponse:
    body = await request.body()
    return JSONResponse({"length": len(body)})


def _starlette_app() -> Starlette:
    return Starlette(
        routes=[
            Route("/id", _echo_request_id),
            Route("/upload", _body_length, methods=["POST"]),
        ]
    )


@pytest.fixture
def request_id_client() -> TestClient:
    return TestClient(RequestIdMiddleware(_starlette_app()))


@pytest.fixture
def limited_client() -> TestClient:
    return TestClient(BodySizeLimitMiddleware(_starlette_app(), max_bytes=SMALL_LIMIT))


@pytest.fixture
def full_app() -> FastAPI:
    app = create_app()

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("kaboom")

    @app.post("/model")
    def model_body(payload: EchoBody) -> dict[str, int]:
        return {"length": len(payload.text)}

    @app.post("/raw")
    async def raw_body(request: Request) -> dict[str, int]:
        return {"length": len(await request.body())}

    return app


def _chunks(total: int, chunk_size: int = 1_000_000) -> Iterator[bytes]:
    sent = 0
    while sent < total:
        size = min(chunk_size, total - sent)
        sent += size
        yield b"x" * size


# --- resolve_request_id ---------------------------------------------------------------


def test_resolve_request_id_valid_incoming_returns_it() -> None:
    assert resolve_request_id("abc-123-XYZ") == "abc-123-XYZ"


@pytest.mark.parametrize("incoming", [None, "", "a" * 65, "bad id", "id\nnewline", "<script>"])
def test_resolve_request_id_missing_or_unsafe_generates_uuid_hex(incoming: str | None) -> None:
    assert UUID_HEX.fullmatch(resolve_request_id(incoming))


# --- RequestIdMiddleware --------------------------------------------------------------


def test_request_id_middleware_no_header_generates_id(request_id_client: TestClient) -> None:
    response = request_id_client.get("/id")

    request_id = response.headers["X-Request-ID"]
    assert UUID_HEX.fullmatch(request_id)
    assert response.json() == {"request_id": request_id}


def test_request_id_middleware_valid_header_echoes_it(request_id_client: TestClient) -> None:
    response = request_id_client.get("/id", headers={"X-Request-ID": "client-req-42"})

    assert response.headers["X-Request-ID"] == "client-req-42"
    assert response.json() == {"request_id": "client-req-42"}


def test_request_id_middleware_invalid_header_replaces_it(request_id_client: TestClient) -> None:
    response = request_id_client.get("/id", headers={"X-Request-ID": "x" * 65})

    assert UUID_HEX.fullmatch(response.headers["X-Request-ID"])


def test_request_id_middleware_not_found_has_header(request_id_client: TestClient) -> None:
    response = request_id_client.get("/missing")

    assert response.status_code == 404
    assert "X-Request-ID" in response.headers


def test_request_id_middleware_after_request_resets_context(
    request_id_client: TestClient,
) -> None:
    request_id_client.get("/id", headers={"X-Request-ID": "scoped-id"})

    assert get_request_id() == "-"


def test_create_app_unhandled_exception_500_has_request_id(full_app: FastAPI) -> None:
    client = TestClient(full_app, raise_server_exceptions=False)

    response = client.get("/boom", headers={"X-Request-ID": "trace-500"})

    assert response.status_code == 500
    assert response.headers["X-Request-ID"] == "trace-500"


def test_create_app_success_has_request_id(full_app: FastAPI) -> None:
    response = TestClient(full_app).get("/openapi.json")

    assert response.status_code == 200
    assert UUID_HEX.fullmatch(response.headers["X-Request-ID"])


# --- BodySizeLimitMiddleware ----------------------------------------------------------


def test_body_size_limit_default_is_five_megabytes() -> None:
    assert MAX_REQUEST_BODY_BYTES == 5_000_000
    assert BodySizeLimitMiddleware(_starlette_app()).max_bytes == 5_000_000


def test_body_size_limit_non_positive_max_raises() -> None:
    with pytest.raises(ValueError, match="positive"):
        BodySizeLimitMiddleware(_starlette_app(), max_bytes=0)


def test_body_size_limit_under_limit_passes(limited_client: TestClient) -> None:
    response = limited_client.post("/upload", content=b"x" * SMALL_LIMIT)

    assert response.status_code == 200
    assert response.json() == {"length": SMALL_LIMIT}


def test_body_size_limit_content_length_over_limit_returns_413(
    limited_client: TestClient,
) -> None:
    response = limited_client.post("/upload", content=b"x" * (SMALL_LIMIT + 1))

    assert response.status_code == 413
    assert response.json() == {
        "error": {
            "code": "PAYLOAD_TOO_LARGE",
            "message": f"Request body exceeds the maximum size of {SMALL_LIMIT} bytes.",
            "details": {"max_bytes": SMALL_LIMIT},
        }
    }


def test_body_size_limit_chunked_over_limit_returns_413(limited_client: TestClient) -> None:
    response = limited_client.post("/upload", content=_chunks(SMALL_LIMIT * 3, chunk_size=40))

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_body_size_limit_chunked_under_limit_passes(limited_client: TestClient) -> None:
    response = limited_client.post("/upload", content=_chunks(SMALL_LIMIT, chunk_size=30))

    assert response.status_code == 200
    assert response.json() == {"length": SMALL_LIMIT}


def test_create_app_chunked_body_over_5mb_returns_413_with_request_id(full_app: FastAPI) -> None:
    client = TestClient(full_app)

    response = client.post(
        "/raw", content=_chunks(MAX_REQUEST_BODY_BYTES + 1), headers={"X-Request-ID": "big-1"}
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"
    assert response.headers["X-Request-ID"] == "big-1"


def test_create_app_model_body_over_5mb_returns_413_not_400(full_app: FastAPI) -> None:
    client = TestClient(full_app)

    response = client.post(
        "/model",
        content=_chunks(MAX_REQUEST_BODY_BYTES + 1),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_create_app_declared_length_over_5mb_returns_413(full_app: FastAPI) -> None:
    response = TestClient(full_app).post("/raw", content=b"x" * (MAX_REQUEST_BODY_BYTES + 1))

    assert response.status_code == 413
    assert "X-Request-ID" in response.headers
