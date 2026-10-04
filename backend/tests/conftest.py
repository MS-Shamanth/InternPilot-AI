"""Shared pytest fixtures for the backend test suite (design.md §16).

`DATABASE_URL` is required at runtime, so it is set here at import time, before any `app`
module is imported: `TEST_DATABASE_URL` when provided (e.g. PostgreSQL), else in-memory SQLite.
A plain `pytest` therefore needs no `.env`. Each test gets a freshly created schema that is
dropped afterwards.
"""

import os

SQLITE_MEMORY_URL = "sqlite+pysqlite:///:memory:"
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL") or SQLITE_MEMORY_URL
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from collections.abc import Callable, Iterator  # noqa: E402
from datetime import UTC, datetime  # noqa: E402

import pytest  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from hypothesis import settings  # noqa: E402
from sqlalchemy.engine import Engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.clock import Clock, FixedClock  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.database import (  # noqa: E402
    create_db_engine,
    get_health_session,
    get_session,
)
from app.core.deps import get_clock  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import Base, Job, User  # noqa: E402

get_settings.cache_clear()

# Shared Hypothesis profile (design.md §16, §17): reproducible runs, no flaky deadlines.
settings.register_profile("internpilot", max_examples=200, derandomize=True, deadline=None)
settings.load_profile("internpilot")

FIXED_NOW = datetime(2025, 1, 15, 9, 30, tzinfo=UTC)
DEMO_EMAIL = "demo@internpilot.dev"
DEMO_CREATED_AT = datetime(2024, 12, 1, 8, 0, tzinfo=UTC)


@pytest.fixture
def db_engine() -> Iterator[Engine]:
    engine = create_db_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def db_session(db_engine: Engine) -> Iterator[Session]:
    with Session(db_engine, expire_on_commit=True) as session:
        yield session
        session.rollback()


@pytest.fixture
def fixed_clock() -> FixedClock:
    return FixedClock(FIXED_NOW)


@pytest.fixture
def app(db_session: Session, fixed_clock: FixedClock) -> FastAPI:
    """App wired to the test session and a fixed clock; no real engine is ever created."""
    application = create_app()

    def override_get_session() -> Iterator[Session]:
        yield db_session

    def override_get_clock() -> Clock:
        return fixed_clock

    application.dependency_overrides[get_session] = override_get_session
    application.dependency_overrides[get_health_session] = override_get_session
    application.dependency_overrides[get_clock] = override_get_clock
    return application


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def demo_user(db_session: Session) -> User:
    """The seeded demo identity (`seed_key='demo'`), committed with fixed timestamps."""
    user = User(
        name="Demo Student",
        email=DEMO_EMAIL,
        seed_key="demo",
        created_at=DEMO_CREATED_AT,
        updated_at=DEMO_CREATED_AT,
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def make_user(db_session: Session) -> Callable[..., User]:
    def factory(email: str = DEMO_EMAIL, **overrides: object) -> User:
        user = User(name="Demo Student", email=email, **overrides)
        db_session.add(user)
        db_session.flush()
        return user

    return factory


@pytest.fixture
def make_job(db_session: Session) -> Callable[..., Job]:
    def factory(suffix: str = "1", **overrides: object) -> Job:
        values: dict[str, object] = {
            "source": "seed",
            "external_id": f"ext-{suffix}",
            "dedupe_fingerprint": suffix.rjust(64, "0"),
            "title": "Frontend Intern",
            "company": "Example Co",
            "location": "Remote",
            "employment_type": "internship",
            "work_mode": "remote",
            "description": "Build UI components.",
            "application_url": "https://jobs.example.com/1",
            "discovered_at": FIXED_NOW,
        }
        values.update(overrides)
        job = Job(**values)
        db_session.add(job)
        db_session.flush()
        return job

    return factory
