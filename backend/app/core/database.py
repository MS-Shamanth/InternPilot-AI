"""Database engine, session factory and the `get_session` dependency (design.md §3, §16).

The engine and session factory are built lazily from `Settings` and cached once per process;
there is no module-level session. Services own the unit of work (commit/rollback); this module
only guarantees that a request's session is rolled back on error and always closed. Tests
replace the whole thing with `app.dependency_overrides[get_session]`.
"""

import logging
from collections.abc import Iterator
from functools import lru_cache

import sqlalchemy as sa
from sqlalchemy.engine import URL, Engine, make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings

logger = logging.getLogger(__name__)

SQLITE_MEMORY_DATABASES = frozenset({"", ":memory:"})
# Hosted Postgres (e.g. Render) hands out driver-less URLs; this app ships psycopg 3.
POSTGRES_DRIVERLESS_NAMES = frozenset({"postgres", "postgresql"})
PSYCOPG_DRIVER = "postgresql+psycopg"


def normalize_database_url(database_url: str) -> URL:
    """Parse `database_url`, mapping `postgres://`/`postgresql://` onto the psycopg 3 driver."""
    url = make_url(database_url)
    if url.drivername in POSTGRES_DRIVERLESS_NAMES:
        return url.set(drivername=PSYCOPG_DRIVER)
    return url


def _enable_sqlite_foreign_keys(dbapi_connection: object, _connection_record: object) -> None:
    """SQLite ignores foreign keys (and therefore cascades) unless enabled per connection."""
    cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]  # DBAPI connection
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def create_db_engine(database_url: str) -> Engine:
    """Create an engine for `database_url` with dialect-appropriate options.

    SQLite: shared across threads (the TestClient runs sync routes in a thread pool), foreign
    keys enabled, and a single shared connection for in-memory databases so every session sees
    the same data. Other databases: `pool_pre_ping` to survive dropped connections.
    """
    url = normalize_database_url(database_url)
    if url.get_backend_name() != "sqlite":
        engine = sa.create_engine(url, pool_pre_ping=True)
    elif (url.database or "") in SQLITE_MEMORY_DATABASES:
        engine = sa.create_engine(
            url, connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
    else:
        engine = sa.create_engine(url, connect_args={"check_same_thread": False})
    if url.get_backend_name() == "sqlite":
        sa.event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    # Only the backend name is logged: the URL may contain credentials.
    logger.info("Database engine created (backend=%s)", url.get_backend_name())
    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Sessions with explicit transactions; services decide when to commit."""
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Process-wide engine built from `DATABASE_URL` on first use."""
    return create_db_engine(get_settings().database_url.get_secret_value())


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    """Process-wide session factory bound to `get_engine()`."""
    return create_session_factory(get_engine())


def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    """Yield one session; roll back if the consumer raises, close it in every case."""
    session = factory()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request from the process-wide factory."""
    yield from session_scope(get_session_factory())


def get_health_session() -> Iterator[Session | None]:
    """FastAPI dependency for `GET /api/health`: like `get_session`, but yields `None` when no
    session can be obtained (invalid URL, missing dialect or driver) so the health route can
    answer with its degraded body instead of an error (R12.6). Only the exception type is
    logged: the message may contain the database URL.
    """
    try:
        factory = get_session_factory()
    except (SQLAlchemyError, ImportError) as exc:
        logger.warning("Health check could not create a database session: %s", type(exc).__name__)
        yield None
        return
    yield from session_scope(factory)
