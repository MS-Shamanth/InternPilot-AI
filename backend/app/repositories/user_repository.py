"""Queries for the `users` aggregate (design.md §3.1, §4.2)."""

from collections.abc import Iterable

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.models import Skill, User, UserSkill


class UserRepository:
    """Read and persist users; the caller's service owns the transaction."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, user_id: int) -> User | None:
        return self._session.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        """Exact match on the stored (lowercase) email; callers pass a normalized value."""
        return self._session.scalars(sa.select(User).where(User.email == email)).one_or_none()

    def get_by_seed_key(self, seed_key: str) -> User | None:
        """The user created by the seed under `seed_key` (e.g. `'demo'`), if any."""
        return self._session.scalars(sa.select(User).where(User.seed_key == seed_key)).one_or_none()

    def add(self, user: User) -> User:
        """Stage a new user and flush so it has an id; no commit."""
        self._session.add(user)
        self._session.flush()
        return user

    def replace_skills(self, user: User, skill_ids: Iterable[int]) -> None:
        """Make the user's technical skills exactly `skill_ids`.

        Rows are diffed rather than recreated, so unchanged links are kept and the composite
        primary key is never re-inserted within one flush.
        """
        wanted = set(skill_ids)
        user.user_skills = [link for link in user.user_skills if link.skill_id in wanted]
        kept = {link.skill_id for link in user.user_skills}
        for skill_id in sorted(wanted - kept):
            user.user_skills.append(UserSkill(skill_id=skill_id))
        self._session.flush()

    def list_skills(self, user_id: int) -> list[Skill]:
        """The user's technical skills ordered by normalized name."""
        statement = (
            sa.select(Skill)
            .join(UserSkill, UserSkill.skill_id == Skill.id)
            .where(UserSkill.user_id == user_id)
            .order_by(Skill.normalized_name)
        )
        return list(self._session.scalars(statement).all())
