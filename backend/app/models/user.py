"""`users` table (design.md §4.1)."""

from typing import TYPE_CHECKING, Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    EDUCATION_LEVELS,
    EXPERIENCE_LEVELS,
    Base,
    PortableJSON,
    TimestampMixin,
    check_in,
    empty_json_list,
)

if TYPE_CHECKING:
    from app.models.skill import UserSkill

JSONList = list[Any]

# `users.seed_key` of the seeded demo user: its stable identity for default-user resolution and
# seed idempotency (design.md §12, §13.2); the email may be edited.
DEMO_SEED_KEY = "demo"


class User(TimestampMixin, Base):
    """The profile owner. The demo user is identified by `seed_key='demo'`, not by email."""

    __tablename__ = "users"
    __table_args__ = (
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.UniqueConstraint("seed_key", name="uq_users_seed_key"),
        sa.CheckConstraint(
            check_in("experience_level", EXPERIENCE_LEVELS), name="experience_level"
        ),
        sa.CheckConstraint(check_in("education_level", EDUCATION_LEVELS), name="education_level"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    email: Mapped[str] = mapped_column(sa.String(254), nullable=False)
    seed_key: Mapped[str | None] = mapped_column(sa.String(32))
    location: Mapped[str | None] = mapped_column(sa.String(120))
    experience_level: Mapped[str | None] = mapped_column(sa.String(16))
    education_level: Mapped[str | None] = mapped_column(sa.String(16))
    education: Mapped[JSONList] = mapped_column(
        PortableJSON, nullable=False, default=list, server_default=empty_json_list()
    )
    target_roles: Mapped[JSONList] = mapped_column(
        PortableJSON, nullable=False, default=list, server_default=empty_json_list()
    )
    preferred_locations: Mapped[JSONList] = mapped_column(
        PortableJSON, nullable=False, default=list, server_default=empty_json_list()
    )
    preferred_work_modes: Mapped[JSONList] = mapped_column(
        PortableJSON, nullable=False, default=list, server_default=empty_json_list()
    )
    soft_skills: Mapped[JSONList] = mapped_column(
        PortableJSON, nullable=False, default=list, server_default=empty_json_list()
    )
    projects: Mapped[JSONList] = mapped_column(
        PortableJSON, nullable=False, default=list, server_default=empty_json_list()
    )
    certifications: Mapped[JSONList] = mapped_column(
        PortableJSON, nullable=False, default=list, server_default=empty_json_list()
    )
    resume_text: Mapped[str] = mapped_column(sa.Text, nullable=False, default="", server_default="")
    github_url: Mapped[str | None] = mapped_column(sa.String(300))
    portfolio_url: Mapped[str | None] = mapped_column(sa.String(300))
    linkedin_url: Mapped[str | None] = mapped_column(sa.String(300))

    user_skills: Mapped[list["UserSkill"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
