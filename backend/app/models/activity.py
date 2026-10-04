"""`activity_events` table: durable source for "recent activity" (design.md §4.1, R6.1)."""

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, check_in

ACTIVITY_TYPES: tuple[str, ...] = (
    "application_created",
    "status_changed",
    "application_updated",
    "application_deleted",
    "job_bookmarked",
    "job_hidden",
    "profile_updated",
    "jobs_ingested",
)


class ActivityEvent(CreatedAtMixin, Base):
    """One user-visible event. `application_id` has no FK so history survives deletes."""

    __tablename__ = "activity_events"
    __table_args__ = (
        sa.CheckConstraint(check_in("type", ACTIVITY_TYPES), name="type"),
        sa.Index("ix_activity_user_created", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(sa.String(40), nullable=False)
    job_id: Mapped[int | None] = mapped_column(sa.ForeignKey("jobs.id", ondelete="SET NULL"))
    application_id: Mapped[int | None] = mapped_column(sa.Integer)
    message: Mapped[str] = mapped_column(sa.String(300), nullable=False)
