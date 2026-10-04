"""Initial schema: users, skills, jobs, applications, activity (design.md §4, §4.3).

Hand-written so every constraint and index has an explicit, stable name. Names are wrapped in
`op.f()` so the metadata naming convention is not applied a second time. Value lists are
literal copies (not imports from `app.models`) so this revision never changes retroactively.

Revision ID: 0001_initial
Revises:
Create Date: 2025-01-01 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EXPERIENCE_LEVELS = ("internship", "entry", "junior", "mid", "senior")
EDUCATION_LEVELS = ("high_school", "diploma", "bachelor", "master", "phd")
JOB_SOURCES = ("seed", "fixture", "remotive", "arbeitnow", "payload")
EMPLOYMENT_TYPES = ("internship", "full_time", "part_time", "contract")
WORK_MODES = ("remote", "hybrid", "onsite")
SALARY_PERIODS = ("year", "month", "hour")
APPLICATION_STATUSES = (
    "Saved",
    "Interested",
    "Applied",
    "Assessment",
    "Interview",
    "Rejected",
    "Offer",
    "Withdrawn",
)
ACTIVITY_TYPES = (
    "application_created",
    "status_changed",
    "application_updated",
    "application_deleted",
    "job_bookmarked",
    "job_hidden",
    "profile_updated",
    "jobs_ingested",
)


def _json() -> sa.types.TypeEngine[object]:
    """JSON everywhere, JSONB on PostgreSQL (same as `PortableJSON`)."""
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def _timestamp() -> sa.DateTime:
    """Timezone-aware timestamp (the `UTCDateTime` implementation type)."""
    return sa.DateTime(timezone=True)


def _check_in(column_name: str, values: Sequence[str]) -> str:
    quoted = ", ".join(f"'{value}'" for value in values)
    return f"{column_name} IN ({quoted})"


def _json_list_column(name: str) -> sa.Column[object]:
    return sa.Column(name, _json(), nullable=False, server_default=sa.text("'[]'"))


def _created_at() -> sa.Column[object]:
    return sa.Column("created_at", _timestamp(), nullable=False, server_default=sa.func.now())


def _updated_at() -> sa.Column[object]:
    return sa.Column("updated_at", _timestamp(), nullable=False, server_default=sa.func.now())


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("seed_key", sa.String(32), nullable=True),
        sa.Column("location", sa.String(120), nullable=True),
        sa.Column("experience_level", sa.String(16), nullable=True),
        sa.Column("education_level", sa.String(16), nullable=True),
        _json_list_column("education"),
        _json_list_column("target_roles"),
        _json_list_column("preferred_locations"),
        _json_list_column("preferred_work_modes"),
        _json_list_column("soft_skills"),
        _json_list_column("projects"),
        _json_list_column("certifications"),
        sa.Column("resume_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("github_url", sa.String(300), nullable=True),
        sa.Column("portfolio_url", sa.String(300), nullable=True),
        sa.Column("linkedin_url", sa.String(300), nullable=True),
        _created_at(),
        _updated_at(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
        sa.UniqueConstraint("seed_key", name=op.f("uq_users_seed_key")),
        sa.CheckConstraint(
            _check_in("experience_level", EXPERIENCE_LEVELS),
            name=op.f("ck_users_experience_level"),
        ),
        sa.CheckConstraint(
            _check_in("education_level", EDUCATION_LEVELS),
            name=op.f("ck_users_education_level"),
        ),
    )

    op.create_table(
        "skills",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("normalized_name", sa.String(80), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_skills")),
        sa.UniqueConstraint("normalized_name", name=op.f("uq_skills_normalized_name")),
    )

    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("external_id", sa.String(128), nullable=False),
        sa.Column("dedupe_fingerprint", sa.CHAR(64), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("company", sa.String(200), nullable=False),
        sa.Column("location", sa.String(200), nullable=False),
        sa.Column("employment_type", sa.String(16), nullable=False),
        sa.Column("work_mode", sa.String(8), nullable=False),
        sa.Column("experience_level", sa.String(16), nullable=True),
        sa.Column("min_education_level", sa.String(16), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("salary_min", sa.Integer(), nullable=True),
        sa.Column("salary_max", sa.Integer(), nullable=True),
        sa.Column("salary_currency", sa.CHAR(3), nullable=True),
        sa.Column("salary_period", sa.String(8), nullable=True),
        sa.Column("application_url", sa.String(500), nullable=False),
        sa.Column("deadline", sa.Date(), nullable=True),
        sa.Column("discovered_at", _timestamp(), nullable=False),
        _created_at(),
        _updated_at(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jobs")),
        sa.UniqueConstraint("source", "external_id", name=op.f("uq_jobs_source_external_id")),
        sa.UniqueConstraint("dedupe_fingerprint", name=op.f("uq_jobs_dedupe_fingerprint")),
        sa.CheckConstraint(_check_in("source", JOB_SOURCES), name=op.f("ck_jobs_source")),
        sa.CheckConstraint(
            _check_in("employment_type", EMPLOYMENT_TYPES), name=op.f("ck_jobs_employment_type")
        ),
        sa.CheckConstraint(_check_in("work_mode", WORK_MODES), name=op.f("ck_jobs_work_mode")),
        sa.CheckConstraint(
            _check_in("experience_level", EXPERIENCE_LEVELS),
            name=op.f("ck_jobs_experience_level"),
        ),
        sa.CheckConstraint(
            _check_in("min_education_level", EDUCATION_LEVELS),
            name=op.f("ck_jobs_min_education_level"),
        ),
        sa.CheckConstraint(
            _check_in("salary_period", SALARY_PERIODS), name=op.f("ck_jobs_salary_period")
        ),
        sa.CheckConstraint(
            "salary_min IS NULL OR salary_min >= 0", name=op.f("ck_jobs_salary_min_non_negative")
        ),
        sa.CheckConstraint(
            "salary_max IS NULL OR salary_max >= 0", name=op.f("ck_jobs_salary_max_non_negative")
        ),
        sa.CheckConstraint(
            "salary_min IS NULL OR salary_max IS NULL OR salary_min <= salary_max",
            name=op.f("ck_jobs_salary_range"),
        ),
    )
    op.create_index(op.f("ix_jobs_discovered_at"), "jobs", ["discovered_at"])
    op.create_index(op.f("ix_jobs_deadline"), "jobs", ["deadline"])
    op.create_index(op.f("ix_jobs_employment_type"), "jobs", ["employment_type"])
    op.create_index(op.f("ix_jobs_work_mode"), "jobs", ["work_mode"])

    op.create_table(
        "user_skills",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("skill_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "skill_id", name=op.f("pk_user_skills")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_skills_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["skill_id"],
            ["skills.id"],
            name=op.f("fk_user_skills_skill_id_skills"),
            ondelete="CASCADE",
        ),
    )

    op.create_table(
        "job_skills",
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("skill_id", sa.Integer(), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("job_id", "skill_id", name=op.f("pk_job_skills")),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["jobs.id"],
            name=op.f("fk_job_skills_job_id_jobs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["skill_id"], ["skills.id"], name=op.f("fk_job_skills_skill_id_skills")
        ),
    )

    op.create_table(
        "user_job_states",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("is_bookmarked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_hidden", sa.Boolean(), nullable=False, server_default=sa.false()),
        _updated_at(),
        sa.PrimaryKeyConstraint("user_id", "job_id", name=op.f("pk_user_job_states")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_job_states_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["jobs.id"],
            name=op.f("fk_user_job_states_job_id_jobs"),
            ondelete="CASCADE",
        ),
    )

    op.create_table(
        "applications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("applied_at", sa.Date(), nullable=True),
        sa.Column("deadline", sa.Date(), nullable=True),
        sa.Column("interview_date", _timestamp(), nullable=True),
        sa.Column("recruiter_name", sa.String(120), nullable=True),
        sa.Column("recruiter_email", sa.String(254), nullable=True),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("outcome", sa.String(500), nullable=True),
        _created_at(),
        _updated_at(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_applications")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_applications_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["jobs.id"],
            name=op.f("fk_applications_job_id_jobs"),
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("user_id", "job_id", name=op.f("uq_applications_user_job")),
        sa.CheckConstraint(
            _check_in("status", APPLICATION_STATUSES), name=op.f("ck_applications_status")
        ),
    )
    op.create_index(op.f("ix_applications_user_status"), "applications", ["user_id", "status"])

    op.create_table(
        "activity_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(40), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column("application_id", sa.Integer(), nullable=True),
        sa.Column("message", sa.String(300), nullable=False),
        _created_at(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_activity_events")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_activity_events_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["jobs.id"],
            name=op.f("fk_activity_events_job_id_jobs"),
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(_check_in("type", ACTIVITY_TYPES), name=op.f("ck_activity_events_type")),
    )
    op.create_index(op.f("ix_activity_user_created"), "activity_events", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index(op.f("ix_activity_user_created"), table_name="activity_events")
    op.drop_table("activity_events")
    op.drop_index(op.f("ix_applications_user_status"), table_name="applications")
    op.drop_table("applications")
    op.drop_table("user_job_states")
    op.drop_table("job_skills")
    op.drop_table("user_skills")
    op.drop_index(op.f("ix_jobs_work_mode"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_employment_type"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_deadline"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_discovered_at"), table_name="jobs")
    op.drop_table("jobs")
    op.drop_table("skills")
    op.drop_table("users")
