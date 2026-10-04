"""Alembic `0001_initial` migration tests (design.md §4.3).

Runs on a fresh file-based SQLite database by default, or on `TEST_DATABASE_URL` when set.
Migrations get an open connection via `config.attributes["connection"]`, so no
`DATABASE_URL` is needed.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy.engine import Engine

from app.models import Base

pytestmark = pytest.mark.integration

BACKEND_DIR = Path(__file__).resolve().parents[2]
ALEMBIC_VERSION_TABLE = "alembic_version"
EXPECTED_TABLES = {
    "users",
    "skills",
    "user_skills",
    "jobs",
    "job_skills",
    "user_job_states",
    "applications",
    "activity_events",
}
EXPECTED_UNIQUE = {
    "users": {"uq_users_email", "uq_users_seed_key"},
    "skills": {"uq_skills_normalized_name"},
    "jobs": {"uq_jobs_source_external_id", "uq_jobs_dedupe_fingerprint"},
    "applications": {"uq_applications_user_job"},
}
EXPECTED_CHECKS = {
    "users": {"ck_users_experience_level", "ck_users_education_level"},
    "jobs": {
        "ck_jobs_source",
        "ck_jobs_employment_type",
        "ck_jobs_work_mode",
        "ck_jobs_experience_level",
        "ck_jobs_min_education_level",
        "ck_jobs_salary_period",
        "ck_jobs_salary_min_non_negative",
        "ck_jobs_salary_max_non_negative",
        "ck_jobs_salary_range",
    },
    "applications": {"ck_applications_status"},
    "activity_events": {"ck_activity_events_type"},
}
EXPECTED_INDEXES = {
    "jobs": {
        "ix_jobs_discovered_at",
        "ix_jobs_deadline",
        "ix_jobs_employment_type",
        "ix_jobs_work_mode",
    },
    "applications": {"ix_applications_user_status"},
    "activity_events": {"ix_activity_user_created"},
}
EXPECTED_FOREIGN_KEYS = {
    "user_skills": {"fk_user_skills_user_id_users", "fk_user_skills_skill_id_skills"},
    "job_skills": {"fk_job_skills_job_id_jobs", "fk_job_skills_skill_id_skills"},
    "user_job_states": {"fk_user_job_states_user_id_users", "fk_user_job_states_job_id_jobs"},
    "applications": {"fk_applications_user_id_users", "fk_applications_job_id_jobs"},
    "activity_events": {"fk_activity_events_user_id_users", "fk_activity_events_job_id_jobs"},
}


@pytest.fixture
def migration_engine(tmp_path: Path) -> Iterator[Engine]:
    url = os.environ.get("TEST_DATABASE_URL") or f"sqlite+pysqlite:///{tmp_path / 'migrate.db'}"
    engine = sa.create_engine(url)
    try:
        yield engine
    finally:
        with engine.begin() as connection:
            _run(connection, "downgrade", "base")
            connection.execute(sa.text(f"DROP TABLE IF EXISTS {ALEMBIC_VERSION_TABLE}"))
        engine.dispose()


def _alembic_config(connection: sa.Connection) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.attributes["connection"] = connection
    config.attributes["configure_logger"] = False
    return config


def _run(connection: sa.Connection, action: str, revision: str) -> None:
    config = _alembic_config(connection)
    if action == "upgrade":
        command.upgrade(config, revision)
    else:
        command.downgrade(config, revision)


def _migrate(engine: Engine, action: str, revision: str) -> None:
    with engine.begin() as connection:
        _run(connection, action, revision)


def _app_tables(engine: Engine) -> set[str]:
    return set(sa.inspect(engine).get_table_names()) - {ALEMBIC_VERSION_TABLE}


def test_upgrade_head_creates_every_model_table(migration_engine: Engine) -> None:
    _migrate(migration_engine, "upgrade", "head")

    assert _app_tables(migration_engine) == EXPECTED_TABLES
    assert _app_tables(migration_engine) == set(Base.metadata.tables)


def test_upgrade_head_schema_matches_models_without_differences(
    migration_engine: Engine,
) -> None:
    _migrate(migration_engine, "upgrade", "head")

    with migration_engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        differences = compare_metadata(context, Base.metadata)

    assert differences == []


def test_downgrade_base_removes_every_table(migration_engine: Engine) -> None:
    _migrate(migration_engine, "upgrade", "head")

    _migrate(migration_engine, "downgrade", "base")

    assert _app_tables(migration_engine) == set()


def test_upgrade_downgrade_upgrade_round_trip_succeeds(migration_engine: Engine) -> None:
    _migrate(migration_engine, "upgrade", "head")
    _migrate(migration_engine, "downgrade", "base")

    _migrate(migration_engine, "upgrade", "head")

    assert _app_tables(migration_engine) == EXPECTED_TABLES
    with migration_engine.connect() as connection:
        assert MigrationContext.configure(connection).get_current_revision() == "0001_initial"


def test_upgrade_head_uses_stable_constraint_and_index_names(migration_engine: Engine) -> None:
    _migrate(migration_engine, "upgrade", "head")
    inspector = sa.inspect(migration_engine)

    for table in EXPECTED_TABLES:
        assert inspector.get_pk_constraint(table)["name"] == f"pk_{table}"
    for table, names in EXPECTED_UNIQUE.items():
        assert {uq["name"] for uq in inspector.get_unique_constraints(table)} == names
    for table, names in EXPECTED_CHECKS.items():
        assert {ck["name"] for ck in inspector.get_check_constraints(table)} == names
    for table, names in EXPECTED_INDEXES.items():
        # PostgreSQL also reports the indexes backing unique constraints; those are checked above.
        indexes = inspector.get_indexes(table)
        assert {ix["name"] for ix in indexes if not ix.get("duplicates_constraint")} == names
    for table, names in EXPECTED_FOREIGN_KEYS.items():
        assert {fk["name"] for fk in inspector.get_foreign_keys(table)} == names


def test_upgrade_head_enforces_application_status_check(migration_engine: Engine) -> None:
    _migrate(migration_engine, "upgrade", "head")
    insert_user = sa.text("INSERT INTO users (id, name, email) VALUES (1, 'Demo', 'd@example.com')")
    insert_job = sa.text(
        "INSERT INTO jobs (id, source, external_id, dedupe_fingerprint, title, company, location,"
        " employment_type, work_mode, description, application_url, discovered_at)"
        " VALUES (1, 'seed', 'j1', :fingerprint, 'Intern', 'Acme', 'Remote', 'internship',"
        " 'remote', 'Build things', 'https://example.com/apply', CURRENT_TIMESTAMP)"
    )
    insert_application = sa.text(
        "INSERT INTO applications (user_id, job_id, status) VALUES (1, 1, :status)"
    )
    with migration_engine.begin() as connection:
        connection.execute(insert_user)
        connection.execute(insert_job, {"fingerprint": "a" * 64})

    with pytest.raises(sa.exc.IntegrityError), migration_engine.begin() as connection:
        connection.execute(insert_application, {"status": "applied"})
