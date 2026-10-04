"""Alembic environment (design.md §4.3).

Database selection, first match wins:
1. `config.attributes["connection"]`: an open SQLAlchemy connection (used by tests).
2. `-x db_url=<url>` on the command line.
3. `DATABASE_URL` read through `app.core.config.get_settings()`.

Set `config.attributes["configure_logger"] = False` to keep the caller's logging setup.
"""

from logging.config import fileConfig

import sqlalchemy as sa
from alembic import context
from sqlalchemy.engine import Connection

from app.core.config import get_settings
from app.core.database import normalize_database_url
from app.models import Base

config = context.config
target_metadata = Base.metadata

if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)


def _database_url() -> str:
    override = context.get_x_argument(as_dictionary=True).get("db_url")
    if override:
        return normalize_database_url(override).render_as_string(hide_password=False)
    url = get_settings().database_url.get_secret_value()
    return normalize_database_url(url).render_as_string(hide_password=False)


def _configure(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=connection.dialect.name == "sqlite",
        compare_type=True,
    )


def run_migrations_offline() -> None:
    """Emit SQL to stdout without connecting (`alembic upgrade head --sql`)."""
    url = _database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=url.startswith("sqlite"),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations on a supplied connection or on a new engine for the configured URL."""
    supplied: Connection | None = config.attributes.get("connection")
    if supplied is not None:
        _configure(supplied)
        with context.begin_transaction():
            context.run_migrations()
        return

    engine = sa.create_engine(_database_url(), poolclass=sa.pool.NullPool)
    try:
        with engine.connect() as connection:
            _configure(connection)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
