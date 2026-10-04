"""SkillRepository against a real session (design.md §4.2)."""

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.models import Skill
from app.repositories.skill_repository import SkillRepository

pytestmark = pytest.mark.integration


def skill_count(session: Session) -> int:
    return session.scalar(sa.select(sa.func.count()).select_from(Skill)) or 0


def test_get_or_create_many_new_names_creates_skills_keyed_by_normalized(
    db_session: Session,
) -> None:
    skills = SkillRepository(db_session).get_or_create_many({"react": "React", "python": "Python"})

    assert set(skills) == {"python", "react"}
    assert skills["react"].name == "React"
    assert all(skill.id is not None for skill in skills.values())


def test_get_or_create_many_repeated_call_is_idempotent(db_session: Session) -> None:
    repository = SkillRepository(db_session)
    first = repository.get_or_create_many({"react": "React"})

    second = repository.get_or_create_many({"react": "REACT", "sql": "SQL"})

    assert second["react"].id == first["react"].id
    assert second["react"].name == "React"
    assert skill_count(db_session) == 2


def test_get_or_create_many_empty_input_returns_empty(db_session: Session) -> None:
    assert SkillRepository(db_session).get_or_create_many({}) == {}


def test_get_by_normalized_names_returns_only_existing(db_session: Session) -> None:
    repository = SkillRepository(db_session)
    repository.get_or_create_many({"react": "React"})

    found = repository.get_by_normalized_names(["react", "react", "go"])

    assert list(found) == ["react"]


def test_list_all_orders_by_normalized_name(db_session: Session) -> None:
    repository = SkillRepository(db_session)
    repository.get_or_create_many({"typescript": "TypeScript", "css": "CSS", "react": "React"})

    assert [skill.normalized_name for skill in repository.list_all()] == [
        "css",
        "react",
        "typescript",
    ]
