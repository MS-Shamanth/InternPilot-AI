"""UserRepository against a real session (design.md §4.2)."""

from collections.abc import Callable

import pytest
from sqlalchemy.orm import Session

from app.models import User
from app.repositories.skill_repository import SkillRepository
from app.repositories.user_repository import UserRepository

pytestmark = pytest.mark.integration

UserFactory = Callable[..., User]


def test_add_then_get_by_id_returns_user(db_session: Session) -> None:
    repository = UserRepository(db_session)

    user = repository.add(User(name="Demo Student", email="demo@internpilot.dev"))

    assert repository.get_by_id(user.id) is user
    assert repository.get_by_id(user.id + 1) is None


def test_replace_skills_sets_exact_skill_set(db_session: Session, make_user: UserFactory) -> None:
    user = make_user()
    skills = SkillRepository(db_session).get_or_create_many(
        {"react": "React", "python": "Python", "sql": "SQL"}
    )
    repository = UserRepository(db_session)
    repository.replace_skills(user, [skills["react"].id, skills["python"].id])

    repository.replace_skills(user, [skills["python"].id, skills["sql"].id, skills["sql"].id])

    assert [skill.normalized_name for skill in repository.list_skills(user.id)] == [
        "python",
        "sql",
    ]


def test_replace_skills_empty_clears_skills(db_session: Session, make_user: UserFactory) -> None:
    user = make_user()
    skills = SkillRepository(db_session).get_or_create_many({"react": "React"})
    repository = UserRepository(db_session)
    repository.replace_skills(user, [skills["react"].id])

    repository.replace_skills(user, [])

    assert repository.list_skills(user.id) == []


def test_list_skills_is_scoped_to_user(db_session: Session, make_user: UserFactory) -> None:
    user = make_user()
    other = make_user(email="other@example.com")
    skills = SkillRepository(db_session).get_or_create_many({"react": "React", "go": "Go"})
    repository = UserRepository(db_session)
    repository.replace_skills(user, [skills["react"].id])
    repository.replace_skills(other, [skills["go"].id])

    assert [skill.normalized_name for skill in repository.list_skills(user.id)] == ["react"]
