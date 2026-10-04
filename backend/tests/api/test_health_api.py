"""API tests for `GET /api/health` (R12.2 exemption, R12.5, R12.6, design.md §8, §14)."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import Session

from app.core import database
from app.core.database import create_db_engine, get_health_session
from app.core.version import APP_VERSION
from app.main import create_app

pytestmark = pytest.mark.api

DEGRADED_BODY = {"status": "degraded", "database": "unavailable", "version": APP_VERSION}
LEAK_MARKERS = ("sqlite", "SELECT", "missing-dir", "Traceback", "error")


def _assert_degraded(response_status: int, body: object, text: str) -> None:
    assert response_status == 503
    assert body == DEGRADED_BODY
    for marker in LEAK_MARKERS:
        assert marker not in text


def test_health_database_reachable_returns_ok(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok", "version": APP_VERSION}
    assert response.headers["X-Request-ID"]


def test_health_database_unreachable_returns_degraded_body(app: FastAPI, tmp_path: Path) -> None:
    # A real engine whose database file lives in a directory that does not exist:
    # every connection attempt raises OperationalError.
    broken_engine = create_db_engine(f"sqlite+pysqlite:///{tmp_path / 'missing-dir' / 'x.db'}")

    def broken_session() -> Iterator[Session]:
        with Session(broken_engine) as session:
            yield session

    app.dependency_overrides[get_health_session] = broken_session
    try:
        with TestClient(app, raise_server_exceptions=False) as test_client:
            response = test_client.get("/api/health")
    finally:
        broken_engine.dispose()

    _assert_degraded(response.status_code, response.json(), response.text)
    assert "error" not in response.json()
    assert response.headers["X-Request-ID"]


def test_health_session_cannot_be_created_returns_degraded_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failing_factory() -> None:
        raise ArgumentError("Could not parse SQLAlchemy URL from string 'postgresql://u:pw@x'")

    monkeypatch.setattr(database, "get_session_factory", failing_factory)
    with TestClient(create_app(), raise_server_exceptions=False) as test_client:
        response = test_client.get("/api/health", headers={"X-Request-ID": "health-probe-1"})

    _assert_degraded(response.status_code, response.json(), response.text)
    assert "pw" not in response.text
    assert response.headers["X-Request-ID"] == "health-probe-1"
