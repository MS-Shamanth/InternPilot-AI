"""ApplicationRepository against a real session (design.md §4.2, §8)."""

from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from app.models import Application, Job, User
from app.repositories.application_repository import ApplicationRepository

pytestmark = pytest.mark.integration


@pytest.fixture
def users(make_user: Callable[..., User]) -> tuple[User, User]:
    return make_user(), make_user(email="other@example.com")


def add_application(
    session: Session, user: User, job: Job, status: str = "Saved", **overrides: object
) -> Application:
    return ApplicationRepository(session).add(
        Application(user_id=user.id, job_id=job.id, status=status, **overrides)
    )


def test_get_other_users_application_returns_none(
    db_session: Session, users: tuple[User, User], make_job: Callable[..., Job]
) -> None:
    user, other = users
    application = add_application(db_session, user, make_job())
    repository = ApplicationRepository(db_session)

    assert repository.get(user.id, application.id) is application
    assert repository.get(other.id, application.id) is None


def test_get_by_job_is_scoped_to_user(
    db_session: Session, users: tuple[User, User], make_job: Callable[..., Job]
) -> None:
    user, other = users
    job = make_job()
    application = add_application(db_session, user, job)
    repository = ApplicationRepository(db_session)

    assert repository.get_by_job(user.id, job.id) is application
    assert repository.get_by_job(other.id, job.id) is None


def test_status_by_job_maps_only_users_applications(
    db_session: Session, users: tuple[User, User], make_job: Callable[..., Job]
) -> None:
    user, other = users
    first, second = make_job("1"), make_job("2")
    add_application(db_session, user, first, "Applied")
    add_application(db_session, user, second, "Offer")
    add_application(db_session, other, first, "Rejected")

    assert ApplicationRepository(db_session).status_by_job(user.id) == {
        first.id: "Applied",
        second.id: "Offer",
    }


def test_list_for_user_filters_status_orders_and_loads_job(
    db_session: Session, users: tuple[User, User], make_job: Callable[..., Job]
) -> None:
    user, other = users
    jobs = [make_job(str(n)) for n in range(1, 5)]
    older = add_application(
        db_session, user, jobs[0], "Applied", updated_at=datetime(2025, 1, 1, tzinfo=UTC)
    )
    newer = add_application(
        db_session, user, jobs[1], "Applied", updated_at=datetime(2025, 1, 2, tzinfo=UTC)
    )
    add_application(db_session, user, jobs[2], "Saved", updated_at=datetime(2025, 1, 3, tzinfo=UTC))
    add_application(db_session, other, jobs[3], "Applied")
    db_session.expire_all()
    repository = ApplicationRepository(db_session)

    applied = repository.list_for_user(user.id, statuses=["Applied"])

    assert [application.id for application in applied] == [newer.id, older.id]
    assert all("job" in application.__dict__ for application in applied)
    assert len(repository.list_for_user(user.id)) == 3
    assert len(repository.list_for_user(user.id, limit=2)) == 2


def test_list_all_for_user_and_delete(
    db_session: Session, users: tuple[User, User], make_job: Callable[..., Job]
) -> None:
    user, other = users
    first = add_application(db_session, user, make_job("1"))
    second = add_application(db_session, user, make_job("2"))
    add_application(db_session, other, make_job("3"))
    repository = ApplicationRepository(db_session)

    repository.delete(first)

    assert [application.id for application in repository.list_all_for_user(user.id)] == [second.id]
