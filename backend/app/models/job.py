"""`jobs` and per-user `user_job_states` tables (design.md §4.1)."""

from datetime import date, datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    EDUCATION_LEVELS,
    EXPERIENCE_LEVELS,
    Base,
    TimestampMixin,
    UTCDateTime,
    check_in,
)

if TYPE_CHECKING:
    from app.models.skill import JobSkill

JOB_SOURCES: tuple[str, ...] = ("seed", "fixture", "remotive", "arbeitnow", "payload")
EMPLOYMENT_TYPES: tuple[str, ...] = ("internship", "full_time", "part_time", "contract")
WORK_MODES: tuple[str, ...] = ("remote", "hybrid", "onsite")
SALARY_PERIODS: tuple[str, ...] = ("year", "month", "hour")


class Job(TimestampMixin, Base):
    """A discovered role, deduplicated by (source, external_id) and by content fingerprint."""

    __tablename__ = "jobs"
    __table_args__ = (
        sa.UniqueConstraint("source", "external_id", name="uq_jobs_source_external_id"),
        sa.UniqueConstraint("dedupe_fingerprint", name="uq_jobs_dedupe_fingerprint"),
        sa.CheckConstraint(check_in("source", JOB_SOURCES), name="source"),
        sa.CheckConstraint(check_in("employment_type", EMPLOYMENT_TYPES), name="employment_type"),
        sa.CheckConstraint(check_in("work_mode", WORK_MODES), name="work_mode"),
        sa.CheckConstraint(
            check_in("experience_level", EXPERIENCE_LEVELS), name="experience_level"
        ),
        sa.CheckConstraint(
            check_in("min_education_level", EDUCATION_LEVELS), name="min_education_level"
        ),
        sa.CheckConstraint(check_in("salary_period", SALARY_PERIODS), name="salary_period"),
        sa.CheckConstraint("salary_min IS NULL OR salary_min >= 0", name="salary_min_non_negative"),
        sa.CheckConstraint("salary_max IS NULL OR salary_max >= 0", name="salary_max_non_negative"),
        sa.CheckConstraint(
            "salary_min IS NULL OR salary_max IS NULL OR salary_min <= salary_max",
            name="salary_range",
        ),
        sa.Index("ix_jobs_discovered_at", "discovered_at"),
        sa.Index("ix_jobs_deadline", "deadline"),
        sa.Index("ix_jobs_employment_type", "employment_type"),
        sa.Index("ix_jobs_work_mode", "work_mode"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    external_id: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    dedupe_fingerprint: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    title: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    company: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    location: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    employment_type: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    work_mode: Mapped[str] = mapped_column(sa.String(8), nullable=False)
    experience_level: Mapped[str | None] = mapped_column(sa.String(16))
    min_education_level: Mapped[str | None] = mapped_column(sa.String(16))
    description: Mapped[str] = mapped_column(sa.Text, nullable=False)
    salary_min: Mapped[int | None] = mapped_column(sa.Integer)
    salary_max: Mapped[int | None] = mapped_column(sa.Integer)
    salary_currency: Mapped[str | None] = mapped_column(sa.CHAR(3))
    salary_period: Mapped[str | None] = mapped_column(sa.String(8))
    application_url: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    deadline: Mapped[date | None] = mapped_column(sa.Date)
    discovered_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)

    job_skills: Mapped[list["JobSkill"]] = relationship(
        back_populates="job", cascade="all, delete-orphan", passive_deletes=True
    )


class UserJobState(Base):
    """Per-user bookmark/hide flags for a job; created lazily on first use."""

    __tablename__ = "user_job_states"

    user_id: Mapped[int] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    job_id: Mapped[int] = mapped_column(
        sa.ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True
    )
    is_bookmarked: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=False, server_default=sa.false()
    )
    is_hidden: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=False, server_default=sa.false()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()
    )
