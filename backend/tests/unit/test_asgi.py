"""Unit tests for the production ASGI factory `app.asgi.build_app` (design.md §18)."""

import logging
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI

from app.asgi import build_app
from app.core.config import ConfigurationError, get_settings

pytestmark = pytest.mark.unit

DB_URL = "sqlite+pysqlite:///:memory:"


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    """No local .env, fresh settings cache, and the root logger restored afterwards."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    root = logging.getLogger()
    level, handlers = root.level, list(root.handlers)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
    root.handlers[:] = handlers
    root.setLevel(level)


def test_build_app_log_level_env_applies_to_root_logger(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", DB_URL)
    monkeypatch.setenv("LOG_LEVEL", "warning")

    app = build_app()

    assert isinstance(app, FastAPI)
    assert logging.getLogger().level == logging.WARNING


def test_build_app_missing_database_url_raises_configuration_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(ConfigurationError, match="DATABASE_URL is required"):
        build_app()
