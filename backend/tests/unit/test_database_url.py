"""Unit tests for `normalize_database_url` (hosted Postgres URLs, design.md §18)."""

import pytest

from app.core.database import normalize_database_url

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "raw",
    ["postgres://u:pw@db.example.com/app", "postgresql://u:pw@db.example.com/app"],
)
def test_normalize_database_url_driverless_postgres_uses_psycopg(raw: str) -> None:
    assert normalize_database_url(raw).drivername == "postgresql+psycopg"


@pytest.mark.parametrize(
    "raw", ["postgresql+psycopg://u:pw@db.example.com/app", "sqlite+pysqlite:///:memory:"]
)
def test_normalize_database_url_explicit_driver_is_unchanged(raw: str) -> None:
    assert normalize_database_url(raw).drivername == raw.split("://", 1)[0]
