"""Queries for the `jobs` aggregate and its `job_skills` links (design.md §3.3, §4.1, §8).

`search` applies SQL-level filters only. Scoring, `min_score`, sorting by score and pagination
happen in `JobService` because scores depend on the live profile (§3.3).
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.sql.base import ExecutableOption

from app.models import Job, JobSkill, Skill, UserJobState

LIKE_ESCAPE_CHAR = "\\"


def escape_like(term: str) -> str:
    """Escape LIKE wildcards so `%` and `_` in user input match literally."""
    return (
        term.replace(LIKE_ESCAPE_CHAR, LIKE_ESCAPE_CHAR * 2)
        .replace("%", f"{LIKE_ESCAPE_CHAR}%")
        .replace("_", f"{LIKE_ESCAPE_CHAR}_")
    )


def _contains(column: sa.ColumnElement[str], term: str) -> sa.ColumnElement[bool]:
    """Case-insensitive substring match with a bound, escaped pattern."""
    return column.ilike(f"%{escape_like(term)}%", escape=LIKE_ESCAPE_CHAR)


def _with_skills() -> ExecutableOption:
    return selectinload(Job.job_skills).selectinload(JobSkill.skill)


@dataclass(frozen=True)
class JobSearchFilters:
    """SQL-level job list filters. Empty tuples / `None` mean "no filter".

    Multi-valued filters match any of their values; all supplied filters must hold (R2.4).
    `skills` holds normalized skill names. Hidden jobs are excluded unless `include_hidden`.
    """

    q: str | None = None
    employment_types: tuple[str, ...] = ()
    work_modes: tuple[str, ...] = ()
    experience_levels: tuple[str, ...] = ()
    location: str | None = None
    source: str | None = None
    skills: tuple[str, ...] = ()
    bookmarked_only: bool = False
    include_hidden: bool = False


class JobRepository:
    """Read and persist jobs; the caller's service owns the transaction."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, job_id: int) -> Job | None:
        statement = sa.select(Job).where(Job.id == job_id).options(_with_skills())
        return self._session.scalars(statement).one_or_none()

    def get_by_source_external_id(self, source: str, external_id: str) -> Job | None:
        statement = (
            sa.select(Job)
            .where(Job.source == source, Job.external_id == external_id)
            .options(_with_skills())
        )
        return self._session.scalars(statement).one_or_none()

    def get_by_fingerprint(self, fingerprint: str) -> Job | None:
        statement = (
            sa.select(Job).where(Job.dedupe_fingerprint == fingerprint).options(_with_skills())
        )
        return self._session.scalars(statement).one_or_none()

    def add(self, job: Job) -> Job:
        """Stage a new job and flush so it has an id; no commit."""
        self._session.add(job)
        self._session.flush()
        return job

    def count_all(self) -> int:
        return self._session.scalar(sa.select(sa.func.count()).select_from(Job)) or 0

    def list_by_ids(self, job_ids: Iterable[int]) -> list[Job]:
        """Jobs with the given ids (missing ids are ignored), ordered by id."""
        ids = set(job_ids)
        if not ids:
            return []
        statement = sa.select(Job).where(Job.id.in_(ids)).order_by(Job.id).options(_with_skills())
        return list(self._session.scalars(statement).all())

    def search(self, user_id: int, filters: JobSearchFilters) -> list[Job]:
        """Jobs matching every supplied filter for `user_id`, ordered by id, skills loaded."""
        statement = sa.select(Job).outerjoin(
            UserJobState,
            sa.and_(UserJobState.job_id == Job.id, UserJobState.user_id == user_id),
        )
        for condition in self._conditions(filters):
            statement = statement.where(condition)
        statement = statement.order_by(Job.id).options(_with_skills())
        return list(self._session.scalars(statement).all())

    @staticmethod
    def _conditions(filters: JobSearchFilters) -> list[sa.ColumnElement[bool]]:
        """WHERE clauses; flag conditions rely on the per-user outer join in `search`."""
        conditions: list[sa.ColumnElement[bool]] = []
        if filters.q:
            conditions.append(
                sa.or_(
                    _contains(Job.title, filters.q),
                    _contains(Job.company, filters.q),
                    _contains(Job.description, filters.q),
                )
            )
        if filters.employment_types:
            conditions.append(Job.employment_type.in_(filters.employment_types))
        if filters.work_modes:
            conditions.append(Job.work_mode.in_(filters.work_modes))
        if filters.experience_levels:
            conditions.append(Job.experience_level.in_(filters.experience_levels))
        if filters.location:
            conditions.append(_contains(Job.location, filters.location))
        if filters.source:
            conditions.append(Job.source == filters.source)
        if filters.skills:
            has_skill = (
                sa.select(JobSkill.job_id)
                .join(Skill, Skill.id == JobSkill.skill_id)
                .where(JobSkill.job_id == Job.id, Skill.normalized_name.in_(filters.skills))
            )
            conditions.append(has_skill.exists())
        if filters.bookmarked_only:
            conditions.append(UserJobState.is_bookmarked.is_(True))
        if not filters.include_hidden:
            # No state row (NULL from the outer join) means "not hidden".
            conditions.append(
                sa.or_(UserJobState.is_hidden.is_(None), UserJobState.is_hidden.is_(False))
            )
        return conditions

    def replace_skills(
        self, job: Job, required: Iterable[int], preferred: Iterable[int] = ()
    ) -> None:
        """Make the job's skills exactly `required` plus `preferred` (skill ids).

        A skill in both sets is stored once as required (§5.2). Rows are diffed so the
        composite primary key is never re-inserted within one flush.
        """
        wanted: Mapping[int, bool] = {skill_id: False for skill_id in preferred} | {
            skill_id: True for skill_id in required
        }
        job.job_skills = [link for link in job.job_skills if link.skill_id in wanted]
        for link in job.job_skills:
            link.is_required = wanted[link.skill_id]
        kept = {link.skill_id for link in job.job_skills}
        for skill_id in sorted(set(wanted) - kept):
            job.job_skills.append(JobSkill(skill_id=skill_id, is_required=wanted[skill_id]))
        self._session.flush()
