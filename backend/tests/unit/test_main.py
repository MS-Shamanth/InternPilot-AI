"""Smoke tests for the application factory."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import create_app


def test_create_app_called_returns_fastapi_instance() -> None:
    app = create_app()

    assert isinstance(app, FastAPI)
    assert app.title == "InternPilot AI"


def test_create_app_openapi_endpoint_returns_schema() -> None:
    client = TestClient(create_app())

    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert response.json()["info"]["title"] == "InternPilot AI"


def test_create_app_called_twice_returns_independent_apps() -> None:
    first = create_app()
    second = create_app()

    assert first is not second
