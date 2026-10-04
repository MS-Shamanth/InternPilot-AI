"""JobStateRepository against a real session (design.md §4.1, §4.2)."""

from collections.abc import Callable

import pytest
from sqlalchemy.orm import Session

from app.models import Job, User
from app.repositories.job_state_repository import JobStateRepository

pytestmark = pytest.mark.integration


def test_get_or_create_creates_once_with_false_flags(
    db_session: Session, make_user: Callable[..., User], make_job: Callable[..., Job]
) -> None:
    user, job = make_user(), make_job()
    repository = JobStateRepository(db_session)
    assert repository.get(user.id, job.id) is None

    created = repository.get_or_create(user.id, job.id)
    again = repository.get_or_create(user.id, job.id)

    assert again is created
    assert (created.is_bookmarked, created.is_hidden) == (False, False)


def test_flag_queries_are_scoped_to_user(
    db_session: Session, make_user: Callable[..., User], make_job: Callable[..., Job]
) -> None:
    user, other = make_user(), make_user(email="other@example.com")
    first, second, third = make_job("1"), make_job("2"), make_job("3")
    repository = JobStateRepository(db_session)
    repository.get_or_create(user.id, first.id).is_bookmarked = True
    repository.get_or_create(user.id, second.id).is_hidden = True
    repository.get_or_create(other.id, third.id).is_hidden = True
    db_session.flush()

    assert repository.bookmarked_job_ids(user.id) == {first.id}
    assert repository.hidden_job_ids(user.id) == {second.id}
    assert set(repository.for_user(user.id)) == {first.id, second.id}
    assert set(repository.for_user(user.id, [second.id, third.id])) == {second.id}
    assert repository.for_user(user.id, []) == {}
