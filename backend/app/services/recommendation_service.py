"""Recommendations: best-fit visible jobs the user has not acted on yet (R7, design.md §7)."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import Job, User
from app.repositories.application_repository import ApplicationRepository
from app.repositories.job_repository import JobRepository, JobSearchFilters
from app.repositories.job_state_repository import JobStateRepository
from app.schemas.job import JobSummary, Recommendation
from app.schemas.match import match_explanation_from_result
from app.services.application_status import ApplicationStatus
from app.services.job_service import job_summary_fields
from app.services.matching.engine import compute_match
from app.services.matching.types import MatchResult
from app.services.matching_inputs import match_job_from_job, match_profile_from_user

DEFAULT_RECOMMENDATION_LIMIT = 5
# A job stays recommendable while its application (if any) is still pre-submission (R7.2).
OPEN_STATUSES = frozenset({ApplicationStatus.SAVED, ApplicationStatus.INTERESTED})


@dataclass(frozen=True)
class _Scored:
    job: Job
    result: MatchResult


def _rank_key(scored: _Scored) -> tuple[int, bool, int, int]:
    """Score desc, deadline asc with nulls last, id asc (R7.1)."""
    deadline = scored.job.deadline
    return (
        -scored.result.score,
        deadline is None,
        0 if deadline is None else deadline.toordinal(),
        scored.job.id,
    )


class RecommendationService:
    """Rank candidate jobs with the shared matching engine (R3.12)."""

    def __init__(self, session: Session) -> None:
        self._jobs = JobRepository(session)
        self._states = JobStateRepository(session)
        self._applications = ApplicationRepository(session)

    def recommend(
        self, user: User, limit: int = DEFAULT_RECOMMENDATION_LIMIT
    ) -> list[Recommendation]:
        """Up to `limit` non-hidden jobs with no application or a Saved/Interested one."""
        statuses = self._applications.status_by_job(user.id)
        candidates = [
            job
            for job in self._jobs.search(user.id, JobSearchFilters())
            if job.id not in statuses or statuses[job.id] in OPEN_STATUSES
        ]
        profile = match_profile_from_user(user)
        scored = [
            _Scored(job, compute_match(profile, match_job_from_job(job))) for job in candidates
        ]
        top = sorted(scored, key=_rank_key)[:limit]
        states = self._states.for_user(user.id, [item.job.id for item in top])
        return [
            Recommendation(
                job=JobSummary(
                    **job_summary_fields(
                        item.job, states.get(item.job.id), statuses.get(item.job.id)
                    ),
                    match_score=item.result.score,
                ),
                match_explanation=match_explanation_from_result(item.result),
            )
            for item in top
        ]
