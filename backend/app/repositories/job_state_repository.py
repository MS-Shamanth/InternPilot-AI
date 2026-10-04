"""Queries for per-user `user_job_states` (bookmark / hide flags; design.md §4.1)."""

from collections.abc import Iterable

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.models import UserJobState


class JobStateRepository:
    """Per-user job flags; every query is scoped by `user_id`. Never commits."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, user_id: int, job_id: int) -> UserJobState | None:
        return self._session.get(UserJobState, (user_id, job_id))

    def get_or_create(self, user_id: int, job_id: int) -> UserJobState:
        """The state row for (user, job), created lazily with both flags false."""
        state = self.get(user_id, job_id)
        if state is None:
            state = UserJobState(
                user_id=user_id, job_id=job_id, is_bookmarked=False, is_hidden=False
            )
            self._session.add(state)
            self._session.flush()
        return state

    def for_user(
        self, user_id: int, job_ids: Iterable[int] | None = None
    ) -> dict[int, UserJobState]:
        """The user's state rows keyed by job id, optionally limited to `job_ids`."""
        statement = sa.select(UserJobState).where(UserJobState.user_id == user_id)
        if job_ids is not None:
            ids = set(job_ids)
            if not ids:
                return {}
            statement = statement.where(UserJobState.job_id.in_(ids))
        return {state.job_id: state for state in self._session.scalars(statement)}

    def hidden_job_ids(self, user_id: int) -> set[int]:
        return self._flagged_job_ids(user_id, UserJobState.is_hidden)

    def bookmarked_job_ids(self, user_id: int) -> set[int]:
        return self._flagged_job_ids(user_id, UserJobState.is_bookmarked)

    def _flagged_job_ids(self, user_id: int, flag: sa.ColumnElement[bool]) -> set[int]:
        statement = sa.select(UserJobState.job_id).where(
            UserJobState.user_id == user_id, flag.is_(True)
        )
        return set(self._session.scalars(statement).all())
