"""Career dashboard (R6, design.md §7).

`compute_metrics` is pure: it takes frozen facts plus `today`/`now` and returns every numeric
metric, so each definition is unit-testable without a database. `DashboardService` loads the
facts fresh on every request (R6.3), scores jobs with the shared engine and adds recent
activity and top recommendations.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from fractions import Fraction

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.models import User
from app.repositories.activity_repository import ActivityRepository
from app.repositories.application_repository import ApplicationRepository
from app.repositories.job_repository import JobRepository, JobSearchFilters
from app.repositories.job_state_repository import JobStateRepository
from app.schemas.dashboard import (
    ActivityItem,
    Dashboard,
    DeadlineKind,
    ScoreBucket,
    ScoreBucketCount,
    StatusCount,
    TopRecommendation,
    UpcomingDeadline,
    WeeklyApplicationCount,
)
from app.services.application_status import (
    CANONICAL_ORDER,
    SUBMITTED_STATUSES,
    ApplicationStatus,
)
from app.services.matching.engine import compute_match, to_rounded_float
from app.services.matching_inputs import match_job_from_job, match_profile_from_user
from app.services.recommendation_service import RecommendationService

_S = ApplicationStatus

MATCHING_SCORE_THRESHOLD = 60
DEADLINE_WINDOW_DAYS = 14
DEADLINE_LIMIT = 8
WEEKS_SHOWN = 8
TOP_RECOMMENDATIONS = 5
RESPONDED_STATUSES = frozenset({_S.ASSESSMENT, _S.INTERVIEW, _S.OFFER, _S.REJECTED})
INTERVIEW_EXCLUDED_STATUSES = frozenset({_S.REJECTED, _S.WITHDRAWN, _S.OFFER})
DEADLINE_STATUSES = frozenset({_S.SAVED, _S.INTERESTED, _S.APPLIED, _S.ASSESSMENT, _S.INTERVIEW})
# Lower bound of each bucket, in display order; the last bucket includes 100.
SCORE_BUCKETS: tuple[tuple[int, ScoreBucket], ...] = (
    (0, ScoreBucket.B0_19),
    (20, ScoreBucket.B20_39),
    (40, ScoreBucket.B40_59),
    (60, ScoreBucket.B60_79),
    (80, ScoreBucket.B80_100),
)


@dataclass(frozen=True)
class ApplicationFact:
    """One application with its job's display fields; `deadline` is already
    `application.deadline ?? job.deadline`."""

    id: int
    job_id: int
    status: ApplicationStatus
    applied_at: date | None
    deadline: date | None
    interview_date: datetime | None
    title: str
    company: str


@dataclass(frozen=True)
class BookmarkFact:
    """A bookmarked, non-hidden job without an application."""

    job_id: int
    title: str
    company: str
    deadline: date | None


@dataclass(frozen=True)
class DashboardMetrics:
    total_jobs_discovered: int
    matching_jobs: int
    applications_submitted: int
    interviews_scheduled: int
    offers_received: int
    response_rate: float
    upcoming_deadlines: tuple[UpcomingDeadline, ...]
    status_breakdown: tuple[StatusCount, ...]
    applications_over_time: tuple[WeeklyApplicationCount, ...]
    score_distribution: tuple[ScoreBucketCount, ...]


def _is_submitted(app: ApplicationFact) -> bool:
    return app.status in SUBMITTED_STATUSES or (
        app.status is _S.WITHDRAWN and app.applied_at is not None
    )


def _is_interview(app: ApplicationFact, now: datetime) -> bool:
    if app.status is _S.INTERVIEW:
        return True
    upcoming = app.interview_date is not None and app.interview_date >= now
    return upcoming and app.status not in INTERVIEW_EXCLUDED_STATUSES


def response_rate(responded: int, submitted: int) -> float:
    """`responded / submitted * 100`, half-up to one decimal; 0.0 when nothing is submitted."""
    if submitted == 0:
        return 0.0
    return to_rounded_float(Fraction(responded * 100, submitted), 1)


def upcoming_deadlines(
    applications: Sequence[ApplicationFact], bookmarks: Sequence[BookmarkFact], today: date
) -> tuple[UpcomingDeadline, ...]:
    """Deadlines in `[today, today + 14]`, by deadline then job id, at most 8."""
    last_day = today + timedelta(days=DEADLINE_WINDOW_DAYS)
    items = [
        UpcomingDeadline(
            job_id=app.job_id,
            application_id=app.id,
            title=app.title,
            company=app.company,
            deadline=app.deadline,
            days_left=(app.deadline - today).days,
            kind=DeadlineKind.APPLICATION,
        )
        for app in applications
        if app.status in DEADLINE_STATUSES
        and app.deadline is not None
        and today <= app.deadline <= last_day
    ] + [
        UpcomingDeadline(
            job_id=bookmark.job_id,
            application_id=None,
            title=bookmark.title,
            company=bookmark.company,
            deadline=bookmark.deadline,
            days_left=(bookmark.deadline - today).days,
            kind=DeadlineKind.BOOKMARK,
        )
        for bookmark in bookmarks
        if bookmark.deadline is not None and today <= bookmark.deadline <= last_day
    ]
    items.sort(key=lambda item: (item.deadline, item.job_id))
    return tuple(items[:DEADLINE_LIMIT])


def applications_over_time(
    applications: Sequence[ApplicationFact], today: date
) -> tuple[WeeklyApplicationCount, ...]:
    """Applications per ISO week (Monday start) by `applied_at`, last 8 weeks oldest first."""
    current_monday = today - timedelta(days=today.weekday())
    weeks = [current_monday - timedelta(weeks=offset) for offset in range(WEEKS_SHOWN - 1, -1, -1)]
    counts = dict.fromkeys(weeks, 0)
    for app in applications:
        if app.applied_at is None:
            continue
        monday = app.applied_at - timedelta(days=app.applied_at.weekday())
        if monday in counts:
            counts[monday] += 1
    return tuple(WeeklyApplicationCount(week_start=week, count=counts[week]) for week in weeks)


def score_distribution(scores: Sequence[int]) -> tuple[ScoreBucketCount, ...]:
    """Visible-job scores in the five §7 buckets, every bucket present."""
    counts = dict.fromkeys((bucket for _, bucket in SCORE_BUCKETS), 0)
    for score in scores:
        bucket = next(bucket for lower, bucket in reversed(SCORE_BUCKETS) if score >= lower)
        counts[bucket] += 1
    return tuple(ScoreBucketCount(bucket=bucket, count=count) for bucket, count in counts.items())


def compute_metrics(
    applications: Sequence[ApplicationFact],
    scores: Sequence[int],
    today: date,
    now: datetime,
    *,
    total_jobs: int,
    bookmarks: Sequence[BookmarkFact] = (),
) -> DashboardMetrics:
    """Every numeric dashboard metric (design.md §7). `scores` are the non-hidden jobs' scores."""
    submitted = sum(1 for app in applications if _is_submitted(app))
    responded = sum(1 for app in applications if app.status in RESPONDED_STATUSES)
    return DashboardMetrics(
        total_jobs_discovered=total_jobs,
        matching_jobs=sum(1 for score in scores if score >= MATCHING_SCORE_THRESHOLD),
        applications_submitted=submitted,
        interviews_scheduled=sum(1 for app in applications if _is_interview(app, now)),
        offers_received=sum(1 for app in applications if app.status is _S.OFFER),
        response_rate=response_rate(responded, submitted),
        upcoming_deadlines=upcoming_deadlines(applications, bookmarks, today),
        status_breakdown=tuple(
            StatusCount(status=status, count=sum(1 for app in applications if app.status is status))
            for status in CANONICAL_ORDER
        ),
        applications_over_time=applications_over_time(applications, today),
        score_distribution=score_distribution(scores),
    )


class DashboardService:
    """Assemble the dashboard from fresh data on every call (R6.3)."""

    def __init__(self, session: Session, clock: Clock) -> None:
        self._clock = clock
        self._jobs = JobRepository(session)
        self._states = JobStateRepository(session)
        self._applications = ApplicationRepository(session)
        self._activity = ActivityRepository(session)
        self._recommendations = RecommendationService(session)

    def get(self, user: User) -> Dashboard:
        records = self._applications.list_all_for_user(user.id)
        applications = [
            ApplicationFact(
                id=record.id,
                job_id=record.job_id,
                status=ApplicationStatus(record.status),
                applied_at=record.applied_at,
                deadline=record.deadline or record.job.deadline,
                interview_date=record.interview_date,
                title=record.job.title,
                company=record.job.company,
            )
            for record in records
        ]
        visible_jobs = self._jobs.search(user.id, JobSearchFilters())
        profile = match_profile_from_user(user)
        scores = [compute_match(profile, match_job_from_job(job)).score for job in visible_jobs]
        applied_job_ids = {record.job_id for record in records}
        bookmarked_ids = self._states.bookmarked_job_ids(user.id)
        bookmarks = [
            BookmarkFact(job_id=job.id, title=job.title, company=job.company, deadline=job.deadline)
            for job in visible_jobs
            if job.id in bookmarked_ids and job.id not in applied_job_ids
        ]
        metrics = compute_metrics(
            applications,
            scores,
            self._clock.today(),
            self._clock.now(),
            total_jobs=self._jobs.count_all(),
            bookmarks=bookmarks,
        )
        top = self._recommendations.recommend(user, TOP_RECOMMENDATIONS)
        return Dashboard(
            total_jobs_discovered=metrics.total_jobs_discovered,
            matching_jobs=metrics.matching_jobs,
            applications_submitted=metrics.applications_submitted,
            interviews_scheduled=metrics.interviews_scheduled,
            offers_received=metrics.offers_received,
            response_rate=metrics.response_rate,
            upcoming_deadlines=list(metrics.upcoming_deadlines),
            recent_activity=[
                ActivityItem.model_validate(event) for event in self._activity.recent(user.id)
            ],
            top_recommendations=[
                TopRecommendation(
                    job_id=item.job.id,
                    title=item.job.title,
                    company=item.job.company,
                    location=item.job.location,
                    score=item.job.match_score,
                )
                for item in top
            ],
            status_breakdown=list(metrics.status_breakdown),
            applications_over_time=list(metrics.applications_over_time),
            score_distribution=list(metrics.score_distribution),
        )
