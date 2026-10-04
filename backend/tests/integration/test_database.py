"""Integration tests for app.core.database (engine options, session lifecycle, §16)."""

from collections.abc import Iterator
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.core.database import (
    create_db_engine,
    create_session_factory,
    get_engine,
    get_session,
    get_session_factory,
    session_scope,
)
from app.models import User, UserSkill

pytestmark = pytest.mark.integration


class RecordingSession(Session):
    """Real session that records lifecycle calls so the tests can observe them."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self.calls: list[str] = []

    def rollback(self) -> None:
        self.calls.append("rollback")
        super().rollback()

    def close(self) -> None:
        self.calls.append("close")
        super().close()


@pytest.fixture
def recording_factory(db_engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=db_engine, class_=RecordingSession)


def count_users(engine: Engine) -> int:
    with Session(engine) as session:
        return session.scalar(sa.select(sa.func.count()).select_from(User)) or 0


def test_session_scope_consumer_finishes_closes_without_rollback(
    recording_factory: sessionmaker[Session],
) -> None:
    scope = session_scope(recording_factory)
    session = next(scope)

    with pytest.raises(StopIteration):
        next(scope)

    assert isinstance(session, RecordingSession)
    assert session.calls == ["close"]


def test_session_scope_consumer_raises_rolls_back_closes_and_reraises(
    recording_factory: sessionmaker[Session], db_engine: Engine
) -> None:
    scope = session_scope(recording_factory)
    session = next(scope)
    session.add(User(name="Pending", email="pending@example.com"))
    session.flush()

    with pytest.raises(RuntimeError, match="route failed"):
        scope.throw(RuntimeError("route failed"))

    assert isinstance(session, RecordingSession)
    assert session.calls == ["rollback", "close"]
    assert count_users(db_engine) == 0


def test_session_scope_committed_work_is_kept(
    recording_factory: sessionmaker[Session], db_engine: Engine
) -> None:
    scope = session_scope(recording_factory)
    session = next(scope)
    session.add(User(name="Saved", email="saved@example.com"))
    session.commit()

    scope.close()

    assert count_users(db_engine) == 1


def test_session_factory_keeps_attributes_loaded_after_commit(db_engine: Engine) -> None:
    with create_session_factory(db_engine)() as session:
        user = User(name="Kept", email="kept@example.com")
        session.add(user)
        session.commit()

        assert "email" in user.__dict__


def test_create_db_engine_sqlite_memory_shares_one_connection_with_foreign_keys() -> None:
    engine = create_db_engine("sqlite+pysqlite:///:memory:")
    try:
        assert isinstance(engine.pool, StaticPool)
        with engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
    finally:
        engine.dispose()


def test_create_db_engine_sqlite_file_enforces_foreign_keys(tmp_path: Path) -> None:
    engine = create_db_engine(f"sqlite+pysqlite:///{tmp_path / 'fk.db'}")
    try:
        User.metadata.create_all(engine)
        with pytest.raises(IntegrityError), Session(engine) as session:
            session.add(UserSkill(user_id=999, skill_id=999))
            session.flush()
    finally:
        engine.dispose()


def test_create_db_engine_postgres_url_enables_pre_ping() -> None:
    engine = create_db_engine("postgresql+psycopg://user:placeholder@localhost:5432/db")
    try:
        assert engine.pool._pre_ping is True
    finally:
        engine.dispose()


def test_create_db_engine_does_not_log_url_credentials(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level("INFO", logger="app.core.database"):
        create_db_engine("postgresql+psycopg://user:placeholder-pw@localhost:5432/db").dispose()

    assert "placeholder-pw" not in caplog.text
    assert "backend=postgresql" in caplog.text


@pytest.fixture
def process_engine(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Engine]:
    """Point `DATABASE_URL` at a temporary file database and reset the process-wide caches."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{tmp_path / 'process.db'}")
    get_settings.cache_clear()
    get_session_factory.cache_clear()
    get_engine.cache_clear()
    engine = get_engine()
    User.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()
        get_session_factory.cache_clear()
        get_engine.cache_clear()
        get_settings.cache_clear()


def test_get_engine_built_from_settings_and_cached(process_engine: Engine) -> None:
    assert get_engine() is process_engine
    assert get_session_factory() is get_session_factory()
    assert get_session_factory().kw["bind"] is process_engine


def test_get_session_dependency_yields_session_on_configured_engine(
    process_engine: Engine,
) -> None:
    dependency = get_session()
    session = next(dependency)
    session.add(User(name="Dep", email="dep@example.com"))
    session.commit()

    dependency.close()

    assert session.get_bind() is process_engine
    assert count_users(process_engine) == 1


def test_get_session_dependency_error_rolls_back(process_engine: Engine) -> None:
    dependency = get_session()
    session = next(dependency)
    session.add(User(name="Lost", email="lost@example.com"))
    session.flush()

    with pytest.raises(ValueError, match="boom"):
        dependency.throw(ValueError("boom"))

    assert count_users(process_engine) == 0
