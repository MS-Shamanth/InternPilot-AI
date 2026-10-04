"""Queries for the `applications` aggregate (design.md §4.1, §4.2, §8).

Every query takes `user_id`, so another user's application is simply not found.
"""

from collections.abc import Iterable

import sqlalchemy as sa
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.sql.base import ExecutableOption

from app.models import Application, Job, JobSkill

# Kanban list cap (design.md §8 pagination exception).
APPLICATION_LIST_LIMIT = 500


def _with_job() -> ExecutableOption:
    return selectinload(Application.job).selectinload(Job.job_skills).selectinload(JobSkill.skill)


class ApplicationRepository:
    """Read and persist a user's applications; the caller's service owns the transaction."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, user_id: int, application_id: int) -> Application | None:
        statement = (
            sa.select(Application)
            .where(Application.id == application_id, Application.user_id == user_id)
            .options(_with_job())
        )
        return self._session.scalars(statement).one_or_none()

    def get_by_job(self, user_id: int, job_id: int) -> Application | None:
        statement = (
            sa.select(Application)
            .where(Application.user_id == user_id, Application.job_id == job_id)
            .options(_with_job())
        )
        return self._session.scalars(statement).one_or_none()

    def list_for_user(
        self,
        user_id: int,
        statuses: Iterable[str] | None = None,
        limit: int = APPLICATION_LIST_LIMIT,
    ) -> list[Application]:
        """The user's applications (optionally by status), newest update first, capped."""
        statement = sa.select(Application).where(Application.user_id == user_id)
        if statuses is not None:
            statement = statement.where(Application.status.in_(set(statuses)))
        statement = (
            statement.order_by(Application.updated_at.desc(), Application.id.desc())
            .limit(limit)
            .options(_with_job())
        )
        return list(self._session.scalars(statement).all())

    def list_all_for_user(self, user_id: int) -> list[Application]:
        """Every application of the user (dashboard input), ordered by id, jobs loaded."""
        statement = (
            sa.select(Application)
            .where(Application.user_id == user_id)
            .order_by(Application.id)
            .options(_with_job())
        )
        return list(self._session.scalars(statement).all())

    def status_by_job(self, user_id: int) -> dict[int, str]:
        """The user's application status keyed by job id."""
        statement = sa.select(Application.job_id, Application.status).where(
            Application.user_id == user_id
        )
        return {job_id: status for job_id, status in self._session.execute(statement)}

    def add(self, application: Application) -> Application:
        """Stage a new application and flush so it has an id; no commit."""
        self._session.add(application)
        self._session.flush()
        return application

    def delete(self, application: Application) -> None:
        self._session.delete(application)
        self._session.flush()
