"""Queries for the shared `skills` catalog (design.md §4.1, §4.2)."""

from collections.abc import Iterable, Mapping

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.models import Skill


class SkillRepository:
    """Look up and create catalog skills keyed by their normalized name; never commits."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_normalized_names(self, normalized_names: Iterable[str]) -> dict[str, Skill]:
        """Existing skills for the given normalized names, keyed by normalized name."""
        names = set(normalized_names)
        if not names:
            return {}
        statement = sa.select(Skill).where(Skill.normalized_name.in_(names))
        return {skill.normalized_name: skill for skill in self._session.scalars(statement)}

    def get_or_create_many(self, display_by_normalized: Mapping[str, str]) -> dict[str, Skill]:
        """Return a skill for every normalized name, inserting the missing ones.

        `display_by_normalized` maps an already-normalized name to its display name (callers
        normalize first; this layer does not). One SELECT finds existing skills; missing ones
        are added in normalized-name order and flushed so they have ids. Existing display
        names are left unchanged.
        """
        skills = self.get_by_normalized_names(display_by_normalized.keys())
        missing = sorted(set(display_by_normalized) - set(skills))
        for normalized_name in missing:
            skill = Skill(
                name=display_by_normalized[normalized_name], normalized_name=normalized_name
            )
            self._session.add(skill)
            skills[normalized_name] = skill
        if missing:
            self._session.flush()
        return skills

    def list_all(self) -> list[Skill]:
        """Every catalog skill ordered by normalized name."""
        return list(self._session.scalars(sa.select(Skill).order_by(Skill.normalized_name)).all())
