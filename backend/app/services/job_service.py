"""Job discovery use cases: list, detail, bookmark/hide and "mark as applied" (R2, design.md §3.3).

SQL does text/enum/flag filtering (`JobRepository.search`); sorting and pagination happen here
in memory because the default order depends on the live match score (§3.3). Mutations are one
unit of work each: the change and its activity event commit together or not at all.
"""

import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from math import ceil
from types import MappingProxyType

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.errors import NotFoundError
from app.models import Job, User, UserJobState
from app.repositories.activity_repository import ActivityRepository
from app.repositories.application_repository import ApplicationRepository
from app.repositories.job_repository import JobRepository, JobSearchFilters
from app.repositories.job_state_repository import JobStateRepository
from app.schemas.application import Application
from app.schemas.job import (
    JobDetail,
    JobListParams,
    JobSortKey,
    JobState,
    JobSummary,
    Page,
    SortOrder,
)
from app.schemas.match import MatchExplanation, match_explanation_from_result
from app.services.application_service import (
    JOB_NOT_FOUND_MESSAGE,
    ApplicationService,
    MarkAppliedResult,
    activity_message,
    job_label,
)
from app.services.application_status import ApplicationStatus
from app.services.matching.engine import compute_match
from app.services.matching_inputs import match_job_from_job, match_profile_from_user

logger = logging.getLogger(__name__)

JOB_BOOKMARKED_EVENT = "job_bookmarked"
JOB_HIDDEN_EVENT = "job_hidden"

type SortValue = date | int | str
type SortValueOf = Callable[[Job], SortValue | None]


def _discovered_at(job: Job) -> SortValue:
    return job.discovered_at


def _deadline(job: Job) -> SortValue | None:
    return job.deadline


def _title(job: Job) -> SortValue:
    return job.title.casefold()


def _company(job: Job) -> SortValue:
    return job.company.casefold()


def _salary(job: Job) -> SortValue | None:
    """`salary_max ?? salary_min` (design.md §8 sort semantics)."""
    return job.salary_max if job.salary_max is not None else job.salary_min


# Sort keys read from the job itself; `match_score` values come from the engine per request.
SORT_VALUES: Mapping[JobSortKey, SortValueOf] = MappingProxyType(
    {
        JobSortKey.DISCOVERED_AT: _discovered_at,
        JobSortKey.DEADLINE: _deadline,
        JobSortKey.TITLE: _title,
        JobSortKey.COMPANY: _company,
        JobSortKey.SALARY: _salary,
    }
)


def sort_jobs(jobs: Sequence[Job], value_of: SortValueOf, descending: bool) -> list[Job]:
    """Order by `value_of` (R2.5): ties by id ascending, `None` values last in either order.

    Python's sort is stable even with `reverse=True`, so sorting id-ordered input keeps id
    ascending within equal values.
    """
    by_id = sorted(jobs, key=lambda job: job.id)
    present = [job for job in by_id if value_of(job) is not None]
    missing = [job for job in by_id if value_of(job) is None]
    return sorted(present, key=value_of, reverse=descending) + missing


def total_pages(total: int, page_size: int) -> int:
    """Number of pages for `total` items; 0 when there are no items."""
    return ceil(total / page_size)


def page_slice[T](items: Sequence[T], page: int, page_size: int) -> list[T]:
    """The items on 1-based `page`; empty beyond the last page (R2.6)."""
    start = (page - 1) * page_size
    return list(items[start : start + page_size])


@dataclass(frozen=True)
class _Flag:
    """A per-user job flag: its column, the event written when it turns on, and the message."""

    attribute: str
    event_type: str
    verb: str


BOOKMARK_FLAG = _Flag("is_bookmarked", JOB_BOOKMARKED_EVENT, "Bookmarked")
HIDDEN_FLAG = _Flag("is_hidden", JOB_HIDDEN_EVENT, "Hid")


class JobService:
    """Read jobs with the user's flags and application status; set flags; mark applied."""

    def __init__(self, session: Session, clock: Clock) -> None:
        self._session = session
        self._clock = clock
        self._jobs = JobRepository(session)
        self._states = JobStateRepository(session)
        self._applications = ApplicationRepository(session)
        self._activity = ActivityRepository(session)
        self._application_service = ApplicationService(session, clock)

    def list_jobs(self, user: User, params: JobListParams) -> Page[JobSummary]:
        """A page of scored jobs matching every supplied filter (R2.2-R2.7, R3.12).

        Every searched job is scored once against the live profile; `min_score` filters before
        sorting and pagination so `total` counts only qualifying jobs.
        """
        profile = match_profile_from_user(user)
        jobs = self._jobs.search(user.id, self._filters(params))
        scores = {job.id: compute_match(profile, match_job_from_job(job)).score for job in jobs}
        if params.min_score is not None:
            jobs = [job for job in jobs if scores[job.id] >= params.min_score]
        ordered = self._order(jobs, params, scores)
        page_jobs = page_slice(ordered, params.page, params.page_size)
        states = self._states.for_user(user.id, [job.id for job in page_jobs])
        statuses = self._applications.status_by_job(user.id)
        items = [
            JobSummary(
                **job_summary_fields(job, states.get(job.id), statuses.get(job.id)),
                match_score=scores[job.id],
            )
            for job in page_jobs
        ]
        return Page[JobSummary](
            items=items,
            total=len(ordered),
            page=params.page,
            page_size=params.page_size,
            total_pages=total_pages(len(ordered), params.page_size),
        )

    def get_detail(self, user: User, job_id: int) -> JobDetail:
        """One job, hidden or not (R2.7), with the user's application; 404 if unknown (R2.12)."""
        job = self._require_job(job_id)
        record = self._applications.get_by_job(user.id, job.id)
        status = None if record is None else record.status
        fields = job_summary_fields(job, self._states.get(user.id, job.id), status)
        explanation = self._explain(user, job)
        return JobDetail(
            **fields,
            match_score=explanation.score,
            match_explanation=explanation,
            description=job.description,
            application_url=job.application_url,
            min_education_level=job.min_education_level,
            application=None if record is None else Application.model_validate(record),
        )

    def match(self, user: User, job_id: int) -> MatchExplanation:
        """Score one job (hidden or not) against the live profile; 404 if unknown (R3.12)."""
        return self._explain(user, self._require_job(job_id))

    def bookmark(self, user: User, job_id: int) -> JobState:
        """Set the bookmark flag idempotently (R2.8)."""
        return self._set_flag(user, job_id, BOOKMARK_FLAG, value=True)

    def unbookmark(self, user: User, job_id: int) -> JobState:
        """Clear the bookmark flag idempotently (R2.8)."""
        return self._set_flag(user, job_id, BOOKMARK_FLAG, value=False)

    def hide(self, user: User, job_id: int) -> JobState:
        """Set the hidden flag idempotently (R2.9)."""
        return self._set_flag(user, job_id, HIDDEN_FLAG, value=True)

    def unhide(self, user: User, job_id: int) -> JobState:
        """Clear the hidden flag idempotently (R2.9)."""
        return self._set_flag(user, job_id, HIDDEN_FLAG, value=False)

    def apply(self, user: User, job_id: int) -> MarkAppliedResult:
        """Mark the job as applied (R2.10, R2.11); rules live in `ApplicationService`."""
        return self._application_service.mark_applied(user, job_id)

    @staticmethod
    def _filters(params: JobListParams) -> JobSearchFilters:
        return JobSearchFilters(
            q=params.q,
            employment_types=tuple(value.value for value in params.employment_type),
            work_modes=tuple(value.value for value in params.work_mode),
            experience_levels=tuple(value.value for value in params.experience_level),
            location=params.location,
            source=None if params.source is None else params.source.value,
            skills=params.skill_names,
            bookmarked_only=params.bookmarked,
            include_hidden=params.include_hidden,
        )

    @staticmethod
    def _explain(user: User, job: Job) -> MatchExplanation:
        result = compute_match(match_profile_from_user(user), match_job_from_job(job))
        return match_explanation_from_result(result)

    @staticmethod
    def _order(jobs: Sequence[Job], params: JobListParams, scores: Mapping[int, int]) -> list[Job]:
        value_of = SORT_VALUES.get(params.sort) or (lambda job: scores[job.id])
        return sort_jobs(jobs, value_of, descending=params.effective_order is SortOrder.DESC)

    def _set_flag(self, user: User, job_id: int, flag: _Flag, *, value: bool) -> JobState:
        """Set one flag; the state row is created lazily and an event is written only when
        the flag turns on. Repeating a request (or clearing an unset flag) changes nothing."""
        try:
            job = self._require_job(job_id)
            state = self._states.get(user.id, job.id)
            current = False if state is None else getattr(state, flag.attribute)
            if current == value:
                return self._state_schema(job.id, state)
            state = state or self._states.get_or_create(user.id, job.id)
            now = self._clock.now()
            setattr(state, flag.attribute, value)
            state.updated_at = now
            if value:
                self._activity.add(
                    user.id,
                    flag.event_type,
                    activity_message(f"{flag.verb} {job_label(job)}"),
                    job_id=job.id,
                    created_at=now,
                )
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        logger.info("Job %d %s=%s for user_id=%d", job_id, flag.attribute, value, user.id)
        return self._state_schema(job_id, state)

    def _require_job(self, job_id: int) -> Job:
        job = self._jobs.get_by_id(job_id)
        if job is None:
            raise NotFoundError(JOB_NOT_FOUND_MESSAGE)
        return job

    @staticmethod
    def _state_schema(job_id: int, state: UserJobState | None) -> JobState:
        if state is None:
            return JobState(job_id=job_id, is_bookmarked=False, is_hidden=False)
        return JobState(job_id=job_id, is_bookmarked=state.is_bookmarked, is_hidden=state.is_hidden)


def job_summary_fields(
    job: Job, state: UserJobState | None, application_status: str | None
) -> dict[str, object]:
    """Fields shared by `JobSummary` and `JobDetail` (everything except the score)."""
    links = sorted(job.job_skills, key=lambda link: link.skill.normalized_name)
    return {
        "id": job.id,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "employment_type": job.employment_type,
        "work_mode": job.work_mode,
        "experience_level": job.experience_level,
        "salary_min": job.salary_min,
        "salary_max": job.salary_max,
        "salary_currency": job.salary_currency,
        "salary_period": job.salary_period,
        "deadline": job.deadline,
        "source": job.source,
        "discovered_at": job.discovered_at,
        "required_skills": [link.skill.name for link in links if link.is_required],
        "preferred_skills": [link.skill.name for link in links if not link.is_required],
        "is_bookmarked": state is not None and state.is_bookmarked,
        "is_hidden": state is not None and state.is_hidden,
        "application_status": (
            None if application_status is None else ApplicationStatus(application_status)
        ),
    }
