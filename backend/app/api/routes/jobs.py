"""`/api/jobs` discovery, matching and ingestion endpoints (R2, R3.12, R10, design.md §8, §11)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response, status

from app.core.config import Settings, get_settings
from app.core.deps import ClockDep, CurrentUser, SessionDep
from app.schemas.application import Application
from app.schemas.ingest import IngestRequest, IngestResult
from app.schemas.job import JobDetail, JobListParams, JobState, JobSummary, Page
from app.schemas.match import MatchExplanation
from app.services.ingestion.service import IngestionService, IngestionSources, default_sources
from app.services.job_service import JobService

router = APIRouter(prefix="/jobs", tags=["jobs"])


def get_job_service(session: SessionDep, clock: ClockDep) -> JobService:
    return JobService(session, clock)


JobServiceDep = Annotated[JobService, Depends(get_job_service)]
JobId = Annotated[int, Path(ge=1)]
JobListQuery = Annotated[JobListParams, Query()]


def get_ingestion_sources(
    settings: Annotated[Settings, Depends(get_settings)],
) -> IngestionSources:
    """Configured job sources; tests override this to avoid the network."""
    return default_sources(settings)


def get_ingestion_service(
    session: SessionDep,
    clock: ClockDep,
    sources: Annotated[IngestionSources, Depends(get_ingestion_sources)],
) -> IngestionService:
    return IngestionService(session, clock, sources)


IngestionServiceDep = Annotated[IngestionService, Depends(get_ingestion_service)]


@router.post("/ingest")
def ingest_jobs(
    request: IngestRequest, user: CurrentUser, service: IngestionServiceDep
) -> IngestResult:
    """Import jobs from a public API, the local fixtures or a supplied payload; public-source
    failures fall back to fixtures unless `fallback` is false (then 502)."""
    return service.ingest(user, request)


@router.get("")
def list_jobs(user: CurrentUser, service: JobServiceDep, params: JobListQuery) -> Page[JobSummary]:
    """Search, filter, sort and page jobs; repeat `employment_type`/`work_mode`/
    `experience_level` for any-of filters, `skills` is comma-separated."""
    return service.list_jobs(user, params)


@router.get("/{job_id}")
def read_job(job_id: JobId, user: CurrentUser, service: JobServiceDep) -> JobDetail:
    """One job (also when hidden) with the user's flags and application."""
    return service.get_detail(user, job_id)


@router.post("/{job_id}/match")
def match_job(job_id: JobId, user: CurrentUser, service: JobServiceDep) -> MatchExplanation:
    """Compute the match score and explanation for the job against the current profile."""
    return service.match(user, job_id)


@router.put("/{job_id}/bookmark")
def bookmark_job(job_id: JobId, user: CurrentUser, service: JobServiceDep) -> JobState:
    """Bookmark the job (idempotent)."""
    return service.bookmark(user, job_id)


@router.delete("/{job_id}/bookmark")
def unbookmark_job(job_id: JobId, user: CurrentUser, service: JobServiceDep) -> JobState:
    """Remove the bookmark (idempotent)."""
    return service.unbookmark(user, job_id)


@router.put("/{job_id}/hide")
def hide_job(job_id: JobId, user: CurrentUser, service: JobServiceDep) -> JobState:
    """Hide the job from lists and recommendations (idempotent)."""
    return service.hide(user, job_id)


@router.delete("/{job_id}/hide")
def unhide_job(job_id: JobId, user: CurrentUser, service: JobServiceDep) -> JobState:
    """Show the job again (idempotent)."""
    return service.unhide(user, job_id)


@router.post(
    "/{job_id}/apply",
    responses={status.HTTP_201_CREATED: {"model": Application, "description": "Created"}},
)
def apply_to_job(
    job_id: JobId, user: CurrentUser, service: JobServiceDep, response: Response
) -> Application:
    """Mark as applied: 201 when a new application is created, 200 when an existing Saved/
    Interested one moves to Applied or it is already Applied; 409 from any other status."""
    result = service.apply(user, job_id)
    response.status_code = status.HTTP_201_CREATED if result.created else status.HTTP_200_OK
    return result.application
