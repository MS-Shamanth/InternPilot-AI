"""`skills` catalog and the `user_skills` / `job_skills` link tables (design.md §4.1)."""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.job import Job
    from app.models.user import User


class Skill(Base):
    """A canonical skill shared by profiles and jobs."""

    __tablename__ = "skills"
    __table_args__ = (sa.UniqueConstraint("normalized_name", name="uq_skills_normalized_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(sa.String(80), nullable=False)
    normalized_name: Mapped[str] = mapped_column(sa.String(80), nullable=False)


class UserSkill(Base):
    """A technical skill on a user's profile; the composite PK forbids duplicates."""

    __tablename__ = "user_skills"

    user_id: Mapped[int] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    skill_id: Mapped[int] = mapped_column(
        sa.ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True
    )

    user: Mapped["User"] = relationship(back_populates="user_skills")
    skill: Mapped[Skill] = relationship()


class JobSkill(Base):
    """A skill on a job; stored once per job, `is_required` wins over preferred."""

    __tablename__ = "job_skills"

    job_id: Mapped[int] = mapped_column(
        sa.ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True
    )
    skill_id: Mapped[int] = mapped_column(sa.ForeignKey("skills.id"), primary_key=True)
    is_required: Mapped[bool] = mapped_column(sa.Boolean, nullable=False)

    job: Mapped["Job"] = relationship(back_populates="job_skills")
    skill: Mapped[Skill] = relationship()
