"""`applications` table (design.md §4.1, R5)."""

from datetime import date, datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UTCDateTime, check_in

if TYPE_CHECKING:
    from app.models.job import Job

# Canonical order and exact casing (product glossary); mirrored by the DB check constraint.
APPLICATION_STATUSES: tuple[str, ...] = (
    "Saved",
    "Interested",
    "Applied",
    "Assessment",
    "Interview",
    "Rejected",
    "Offer",
    "Withdrawn",
)


class Application(TimestampMixin, Base):
    """A user's tracker record for one job, with exactly one status."""

    __tablename__ = "applications"
    __table_args__ = (
        sa.UniqueConstraint("user_id", "job_id", name="uq_applications_user_job"),
        sa.CheckConstraint(check_in("status", APPLICATION_STATUSES), name="status"),
        sa.Index("ix_applications_user_status", "user_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    job_id: Mapped[int] = mapped_column(
        sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    applied_at: Mapped[date | None] = mapped_column(sa.Date)
    deadline: Mapped[date | None] = mapped_column(sa.Date)
    interview_date: Mapped[datetime | None] = mapped_column(UTCDateTime())
    recruiter_name: Mapped[str | None] = mapped_column(sa.String(120))
    recruiter_email: Mapped[str | None] = mapped_column(sa.String(254))
    notes: Mapped[str] = mapped_column(sa.Text, nullable=False, default="", server_default="")
    outcome: Mapped[str | None] = mapped_column(sa.String(500))

    job: Mapped["Job"] = relationship()
