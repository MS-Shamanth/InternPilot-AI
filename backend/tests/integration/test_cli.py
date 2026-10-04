"""`python -m app.cli` against a temporary SQLite file database (design.md §12)."""

from collections.abc import Iterator
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import Engine

from app.cli import EXIT_FAILURE, EXIT_OK, main
from app.core.config import get_settings
from app.core.database import create_db_engine
from app.models import Application, Base, Job, User

pytestmark = pytest.mark.integration


@pytest.fixture
def file_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Engine]:
    """A schema-initialized SQLite file named by `DATABASE_URL`; settings re-read per test."""
    url = f"sqlite+pysqlite:///{(tmp_path / 'cli.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.delenv("DATA_DIR", raising=False)
    get_settings.cache_clear()
    engine = create_db_engine(url)
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()
        get_settings.cache_clear()


def counts(engine: Engine) -> tuple[int, ...]:
    """(users, jobs, applications)."""
    with engine.connect() as connection:
        return tuple(
            connection.scalar(sa.select(sa.func.count()).select_from(model)) or 0
            for model in (User, Job, Application)
        )


def test_cli_seed_populates_database_and_is_idempotent(file_db: Engine) -> None:
    assert main(["seed"]) == EXIT_OK
    first = counts(file_db)

    assert main(["seed"]) == EXIT_OK

    assert counts(file_db) == first
    users, jobs, applications = first
    assert (users, jobs >= 30, applications >= 10) == (1, True, True)


def test_cli_ingest_fixture_after_seed_succeeds(file_db: Engine) -> None:
    assert main(["seed"]) == EXIT_OK
    _, jobs_before, _ = counts(file_db)

    assert main(["ingest", "--source", "fixture", "--limit", "500"]) == EXIT_OK

    assert counts(file_db)[1] == jobs_before + 3


def test_cli_ingest_without_demo_user_fails(file_db: Engine) -> None:
    assert main(["ingest", "--source", "fixture"]) == EXIT_FAILURE
    assert counts(file_db) == (0, 0, 0)


def test_cli_seed_with_missing_data_files_fails(
    file_db: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("DATA_DIR", str(empty))
    get_settings.cache_clear()

    assert main(["seed"]) == EXIT_FAILURE
    assert counts(file_db) == (0, 0, 0)


@pytest.mark.parametrize("limit", ["0", "501", "many"])
def test_cli_ingest_rejects_invalid_limit(limit: str) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["ingest", "--source", "fixture", "--limit", limit])
    assert exit_info.value.code == 2


def test_cli_without_database_url_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    get_settings.cache_clear()
    try:
        assert main(["seed"]) == EXIT_FAILURE
    finally:
        get_settings.cache_clear()


def test_cli_seed_on_database_without_schema_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{(tmp_path / 'bare.db').as_posix()}")
    monkeypatch.delenv("DATA_DIR", raising=False)
    get_settings.cache_clear()
    try:
        assert main(["seed"]) == EXIT_FAILURE
    finally:
        get_settings.cache_clear()
