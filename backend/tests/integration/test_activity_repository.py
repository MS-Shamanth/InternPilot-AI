"""ActivityRepository against a real session (design.md §7 `recent_activity`)."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.models import User
from app.repositories.activity_repository import ActivityRepository

pytestmark = pytest.mark.integration

BASE_TIME = datetime(2025, 1, 15, 9, 30, tzinfo=UTC)


def test_recent_orders_by_created_at_then_id_desc_and_limits(
    db_session: Session, make_user: Callable[..., User]
) -> None:
    user, other = make_user(), make_user(email="other@example.com")
    repository = ActivityRepository(db_session)
    oldest = repository.add(user.id, "profile_updated", "old", created_at=BASE_TIME)
    tie_first = repository.add(
        user.id, "job_bookmarked", "tie 1", created_at=BASE_TIME + timedelta(hours=1)
    )
    tie_second = repository.add(
        user.id, "job_hidden", "tie 2", created_at=BASE_TIME + timedelta(hours=1)
    )
    newest = repository.add(
        user.id, "status_changed", "new", created_at=BASE_TIME + timedelta(hours=2)
    )
    repository.add(other.id, "profile_updated", "other", created_at=BASE_TIME + timedelta(days=1))

    recent = repository.recent(user.id)

    assert [event.id for event in recent] == [newest.id, tie_second.id, tie_first.id, oldest.id]
    assert [event.id for event in repository.recent(user.id, limit=2)] == [
        newest.id,
        tie_second.id,
    ]


def test_recent_default_limit_is_ten(db_session: Session, make_user: Callable[..., User]) -> None:
    user = make_user()
    repository = ActivityRepository(db_session)
    for minute in range(12):
        repository.add(
            user.id,
            "profile_updated",
            f"event {minute}",
            created_at=BASE_TIME + timedelta(minutes=minute),
        )

    assert len(repository.recent(user.id)) == 10


def test_add_stores_optional_links(db_session: Session, make_user: Callable[..., User]) -> None:
    user = make_user()

    event = ActivityRepository(db_session).add(
        user.id, "application_deleted", "Deleted", application_id=42
    )

    assert (event.job_id, event.application_id, event.message) == (None, 42, "Deleted")
