"""Ingestion orchestration: fetch → normalize → dedupe → persist in one transaction
(R10.4-R10.8, design.md §11.4, §11.5).

All fetching and validation finish before the first write, so a failing source never leaves
partial writes. Public-source failures fall back to the fixture source when requested.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import IngestionSourceUnavailableError
from app.models import Job, User
from app.repositories.activity_repository import ActivityRepository
from app.repositories.job_repository import JobRepository
from app.repositories.skill_repository import SkillRepository
from app.schemas.ingest import (
    INGEST_MAX_ERRORS,
    IngestError,
    IngestRequest,
    IngestResult,
    IngestSourceName,
    JobCreate,
    RawFormat,
)
from app.services.application_service import activity_message
from app.services.ingestion.normalizers import Rejection, fingerprint, normalize_item
from app.services.ingestion.sources import (
    ArbeitnowSource,
    FixtureSource,
    HttpFetcher,
    JobSource,
    PayloadSource,
    RawBatch,
    RemotiveSource,
    SourceUnavailableError,
)
from app.services.matching.normalization import display_skill

logger = logging.getLogger(__name__)

JOBS_INGESTED_EVENT = "jobs_ingested"
PUBLIC_SOURCES = frozenset({IngestSourceName.REMOTIVE, IngestSourceName.ARBEITNOW})
# Fields copied from `JobCreate` on insert and update; source/external_id identify the row and
# `discovered_at` keeps the first-seen time.
MUTABLE_JOB_FIELDS = (
    "title",
    "company",
    "location",
    "employment_type",
    "work_mode",
    "experience_level",
    "min_education_level",
    "description",
    "salary_min",
    "salary_max",
    "salary_currency",
    "salary_period",
    "application_url",
    "deadline",
)


@dataclass(frozen=True)
class IngestionSources:
    """The configured non-payload sources; payload sources are built per request."""

    remotive: JobSource
    arbeitnow: JobSource
    fixture: JobSource


def default_sources(settings: Settings) -> IngestionSources:
    """Real sources from settings: one guarded fetcher shared by the public APIs."""
    fetcher = HttpFetcher(
        settings.ingest_allowed_hosts, settings.ingest_timeout_seconds, settings.ingest_max_bytes
    )
    return IngestionSources(
        remotive=RemotiveSource(fetcher),
        arbeitnow=ArbeitnowSource(fetcher),
        fixture=FixtureSource(settings.data_dir, settings.ingest_max_bytes),
    )


@dataclass
class _Counts:
    created: int = 0
    updated: int = 0
    duplicates: int = 0


@dataclass
class _Prepared:
    """Everything decided before the first write."""

    source: IngestSourceName
    fallback_used: bool
    fetched: int
    jobs: list[JobCreate] = field(default_factory=list)
    errors: list[IngestError] = field(default_factory=list)


class IngestionService:
    """Runs one ingestion; owns the unit of work (one commit, rollback on any failure)."""

    def __init__(self, session: Session, clock: Clock, sources: IngestionSources) -> None:
        self._session = session
        self._clock = clock
        self._sources = sources
        self._jobs = JobRepository(session)
        self._skills = SkillRepository(session)
        self._activity = ActivityRepository(session)

    def ingest(self, user: User, request: IngestRequest) -> IngestResult:
        prepared = self._prepare(request)
        try:
            result = self._store(user, request.source, prepared)
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        _log_result(result)
        return result

    def stage_batches(self, user: User, batches: list[RawBatch]) -> IngestResult:
        """Normalize and persist already-loaded fixture batches without committing.

        Used by the seed (`SeedService`, design.md §12), which owns the unit of work; the result
        reports the run as a `fixture` ingestion. Dedupe rules are the same as `ingest`.
        """
        prepared = _Prepared(IngestSourceName.FIXTURE, fallback_used=False, fetched=0)
        self._normalize(batches, prepared)
        result = self._store(user, IngestSourceName.FIXTURE, prepared)
        _log_result(result)
        return result

    def _store(
        self, user: User, requested_source: IngestSourceName, prepared: _Prepared
    ) -> IngestResult:
        """Write the prepared jobs and the run's activity event (inside the transaction)."""
        counts = self._persist(prepared.jobs, self._clock.now())
        rejected = prepared.fetched - len(prepared.jobs)
        self._activity.add(
            user.id,
            JOBS_INGESTED_EVENT,
            activity_message(
                f"Ingested jobs from {prepared.source}: {counts.created} created, "
                f"{counts.updated} updated, {counts.duplicates} duplicates, {rejected} rejected"
            ),
            created_at=self._clock.now(),
        )
        return IngestResult(
            requested_source=requested_source,
            source=prepared.source,
            fallback_used=prepared.fallback_used,
            fetched=prepared.fetched,
            created=counts.created,
            updated=counts.updated,
            duplicates=counts.duplicates,
            rejected=rejected,
            errors=prepared.errors[:INGEST_MAX_ERRORS],
        )

    # --- fetch and validate (no writes) ---------------------------------------------------

    def _prepare(self, request: IngestRequest) -> _Prepared:
        try:
            batches = self._source_for(request).fetch(request.limit)
            prepared = _Prepared(request.source, fallback_used=False, fetched=0)
        except SourceUnavailableError as error:
            if not request.fallback or request.source not in PUBLIC_SOURCES:
                raise _unavailable(request.source, error) from None
            logger.warning(
                "Ingestion source %s unavailable (%s); using fixtures", request.source, error.reason
            )
            batches = self._fetch_fixture_fallback(request.limit)
            prepared = _Prepared(IngestSourceName.FIXTURE, fallback_used=True, fetched=0)
            reason = f"{request.source}: {error.reason}"
            prepared.errors.append(IngestError(index=None, reason=reason))
        self._normalize(batches, prepared)
        return prepared

    def _source_for(self, request: IngestRequest) -> JobSource:
        match request.source:
            case IngestSourceName.REMOTIVE:
                return self._sources.remotive
            case IngestSourceName.ARBEITNOW:
                return self._sources.arbeitnow
            case IngestSourceName.FIXTURE:
                return self._sources.fixture
            case IngestSourceName.PAYLOAD:
                return PayloadSource(request.format or RawFormat.NORMALIZED, request.payload)

    def _fetch_fixture_fallback(self, limit: int) -> list[RawBatch]:
        try:
            return self._sources.fixture.fetch(limit)
        except SourceUnavailableError as error:
            raise _unavailable(IngestSourceName.FIXTURE, error) from None

    def _normalize(self, batches: list[RawBatch], prepared: _Prepared) -> None:
        """Validate every item; `index` counts items across batches in fetch order."""
        today = self._clock.today()
        index = 0
        for batch in batches:
            for raw in batch.items:
                outcome = normalize_item(raw, batch.format, batch.source, today, index)
                if isinstance(outcome, Rejection):
                    prepared.errors.append(IngestError(index=outcome.index, reason=outcome.reason))
                else:
                    prepared.jobs.append(outcome)
                index += 1
        prepared.fetched = index

    # --- persist (inside the transaction) -------------------------------------------------

    def _persist(self, jobs: list[JobCreate], now: datetime) -> _Counts:
        """Apply §11.4 in input order; every write is flushed so later items see it."""
        counts = _Counts()
        for job_create in jobs:
            job_fingerprint = fingerprint(job_create.title, job_create.company, job_create.location)
            existing = self._jobs.get_by_source_external_id(
                job_create.source, job_create.external_id
            )
            holder = self._jobs.get_by_fingerprint(job_fingerprint)
            if existing is not None:
                if holder is not None and holder.id != existing.id:
                    counts.duplicates += 1
                    continue
                self._write(existing, job_create, job_fingerprint)
                counts.updated += 1
            elif holder is not None:
                counts.duplicates += 1
            else:
                job = Job(
                    source=job_create.source.value,
                    external_id=job_create.external_id,
                    discovered_at=now,
                )
                self._write(job, job_create, job_fingerprint, is_new=True)
                counts.created += 1
        return counts

    def _write(
        self, job: Job, job_create: JobCreate, job_fingerprint: str, *, is_new: bool = False
    ) -> None:
        # Enum fields are `StrEnum`s, so they are stored as their plain string values.
        for name in MUTABLE_JOB_FIELDS:
            setattr(job, name, getattr(job_create, name))
        job.dedupe_fingerprint = job_fingerprint
        if is_new:
            self._jobs.add(job)
        else:
            self._session.flush()
        names = [*job_create.required_skills, *job_create.preferred_skills]
        skills = self._skills.get_or_create_many({name: display_skill(name) for name in names})
        self._jobs.replace_skills(
            job,
            [skills[name].id for name in job_create.required_skills],
            [skills[name].id for name in job_create.preferred_skills],
        )


def _log_result(result: IngestResult) -> None:
    logger.info(
        "Ingestion %s→%s: fetched=%d created=%d updated=%d duplicates=%d rejected=%d",
        result.requested_source,
        result.source,
        result.fetched,
        result.created,
        result.updated,
        result.duplicates,
        result.rejected,
    )


def _unavailable(
    source: IngestSourceName, error: SourceUnavailableError
) -> IngestionSourceUnavailableError:
    return IngestionSourceUnavailableError(details={"source": source.value, "reason": error.reason})
