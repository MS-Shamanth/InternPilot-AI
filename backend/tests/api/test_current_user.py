"""API tests for `get_current_user` (R13.2, R13.2a, R13.3, design.md §13.2)."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.models import User

pytestmark = pytest.mark.api

ME_PATH = "/test/me"
DEMO_EMAIL = "demo@internpilot.dev"
OTHER_EMAIL = "student@example.com"


@pytest.fixture
def me_client(app: FastAPI, client: TestClient) -> TestClient:
    """`client` plus a test-only route that reports the resolved user."""

    @app.get(ME_PATH)
    def read_me(user: CurrentUser) -> dict[str, object]:
        return {"id": user.id, "email": user.email}

    return client


def add_user(session: Session, email: str, seed_key: str | None = None) -> User:
    user = User(name="Test User", email=email, seed_key=seed_key)
    session.add(user)
    session.commit()
    return user


def test_current_user_no_header_resolves_seeded_demo_user(
    me_client: TestClient, db_session: Session
) -> None:
    demo = add_user(db_session, DEMO_EMAIL, seed_key="demo")
    add_user(db_session, OTHER_EMAIL)

    response = me_client.get(ME_PATH)

    assert response.status_code == 200
    assert response.json() == {"id": demo.id, "email": DEMO_EMAIL}


def test_current_user_demo_email_changed_still_resolved_without_header(
    me_client: TestClient, db_session: Session
) -> None:
    demo = add_user(db_session, "renamed@example.com", seed_key="demo")

    response = me_client.get(ME_PATH)

    assert response.status_code == 200
    assert response.json() == {"id": demo.id, "email": "renamed@example.com"}


def test_current_user_header_existing_email_case_insensitive_resolves_that_user(
    me_client: TestClient, db_session: Session
) -> None:
    add_user(db_session, DEMO_EMAIL, seed_key="demo")
    other = add_user(db_session, OTHER_EMAIL)

    response = me_client.get(ME_PATH, headers={"X-Demo-User": "  Student@Example.COM "})

    assert response.status_code == 200
    assert response.json() == {"id": other.id, "email": OTHER_EMAIL}


def test_current_user_header_unknown_email_returns_401_envelope(
    me_client: TestClient, db_session: Session
) -> None:
    add_user(db_session, DEMO_EMAIL, seed_key="demo")

    response = me_client.get(ME_PATH, headers={"X-Demo-User": "nobody@example.com"})

    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "code": "UNKNOWN_DEMO_USER",
            "message": "The requested demo user does not exist.",
            "details": None,
        }
    }
    assert "nobody@example.com" not in response.text
    assert response.headers["X-Request-ID"]


@pytest.mark.parametrize("value", ["", "   ", "not-an-email", "a@b@c", "demo internpilot.dev"])
def test_current_user_header_malformed_returns_401(
    me_client: TestClient, db_session: Session, value: str
) -> None:
    add_user(db_session, DEMO_EMAIL, seed_key="demo")

    response = me_client.get(ME_PATH, headers={"X-Demo-User": value})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNKNOWN_DEMO_USER"


def test_current_user_header_overlong_returns_422_without_echo(
    me_client: TestClient, db_session: Session
) -> None:
    add_user(db_session, DEMO_EMAIL, seed_key="demo")
    overlong = "a" * 250 + "@example.com"

    response = me_client.get(ME_PATH, headers={"X-Demo-User": overlong})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["details"][0]["loc"] == ["header", "X-Demo-User"]
    assert overlong not in response.text


def test_current_user_no_demo_user_seeded_returns_503_envelope(
    me_client: TestClient, db_session: Session
) -> None:
    # A user owning DEMO_USER_EMAIL without the seed key is not the demo user (R13.2a).
    add_user(db_session, DEMO_EMAIL)

    response = me_client.get(ME_PATH)

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "DEMO_USER_NOT_SEEDED",
            "message": "The demo user has not been seeded yet.",
            "details": None,
        }
    }


def test_current_user_header_names_user_while_demo_unseeded_returns_that_user(
    me_client: TestClient, db_session: Session
) -> None:
    other = add_user(db_session, OTHER_EMAIL)

    response = me_client.get(ME_PATH, headers={"X-Demo-User": OTHER_EMAIL})

    assert response.status_code == 200
    assert response.json()["id"] == other.id
