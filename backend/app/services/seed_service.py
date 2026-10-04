"""Idempotent demo seed (R11.1-R11.3, design.md §12).

`SeedService.run()` loads and validates `seed_profile.json`, `seed_jobs.json` and
`seed_applications.json` from `DATA_DIR` before the first write, then in one transaction:
upserts catalog and seed skills, creates the demo user (`seed_key='demo'`) only if missing,
upserts the seed jobs through `IngestionService` and adds the seed applications in the run that
creates the demo user. Re-running never duplicates rows and never overwrites (or re-creates)
the user's profile or application changes. Relative dates resolve against the injected clock.
"""

import json
import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import DemoUserNotSeededError, EmailTakenError, SeedDataError
from app.models import User
from app.models.user import DEMO_SEED_KEY
from app.repositories.job_repository import JobRepository
from app.repositories.skill_repository import SkillRepository
from app.repositories.user_repository import UserRepository
from app.schemas.application import ApplicationCreate
from app.schemas.common import JobSource
from app.schemas.ingest import RawFormat
from app.schemas.profile import ProfileUpdate
from app.schemas.seed import (
    SeedApplication,
    SeedApplications,
    SeedJob,
    SeedJobs,
    parse_seed_profile,
)
from app.services.application_service import ApplicationService
from app.services.ingestion.service import IngestionService, default_sources
from app.services.ingestion.sources import SEED_JOBS_FILE, RawBatch
from app.services.matching.normalization import display_skill, normalize_skills
from app.services.matching.skill_catalog import CATALOG
from app.services.profile_service import ProfileService

logger = logging.getLogger(__name__)

SEED_PROFILE_FILE = "seed_profile.json"
SEED_APPLICATIONS_FILE = "seed_applications.json"
SEED_INTERVIEW_TIME = time(10, 0, tzinfo=UTC)
EMAIL_CONFLICT_MESSAGE = "DEMO_USER_EMAIL already belongs to a user that is not the demo user."


@dataclass(frozen=True)
class SeedData:
    """The validated contents of the three seed files."""

    profile: ProfileUpdate
    jobs: tuple[SeedJob, ...]
    applications: tuple[SeedApplication, ...]

    def skill_names(self) -> frozenset[str]:
        """Normalized names of every catalog skill and every skill used by the seed files."""
        job_skills = {
            name for job in self.jobs for name in (*job.required_skills, *job.preferred_skills)
        }
        return frozenset(CATALOG) | normalize_skills(self.profile.technical_skills) | job_skills


@dataclass(frozen=True)
class SeedSummary:
    """What one seed run changed."""

    user_created: bool
    skills_created: int
    jobs_created: int
    jobs_updated: int
    jobs_duplicates: int
    applications_created: int
    applications_skipped: int


def _describe(error: ValidationError) -> str:
    """`field: message` pairs without input values."""
    parts = []
    for item in error.errors(include_input=False, include_url=False, include_context=False):
        location = ".".join(str(part) for part in item["loc"]) or "file"
        parts.append(f"{location}: {item['msg']}")
    return "; ".join(parts)


def _read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SeedDataError(f"{path.name}: file not found") from None
    except (OSError, UnicodeDecodeError):
        raise SeedDataError(f"{path.name}: file could not be read") from None
    except json.JSONDecodeError:
        raise SeedDataError(f"{path.name}: invalid JSON") from None


def _invalid(file_name: str, error: ValueError) -> SeedDataError:
    message = _describe(error) if isinstance(error, ValidationError) else str(error)
    return SeedDataError(f"{file_name}: {message}")


def load_seed_data(data_dir: Path, demo_name: str, demo_email: str) -> SeedData:
    """Read and validate the seed files; raises `SeedDataError` naming the bad file."""
    try:
        profile = parse_seed_profile(
            _read_json(data_dir / SEED_PROFILE_FILE), demo_name, demo_email
        )
    except ValueError as error:
        raise _invalid(SEED_PROFILE_FILE, error) from None
    try:
        jobs = SeedJobs.model_validate(_read_json(data_dir / SEED_JOBS_FILE)).root
    except ValueError as error:
        raise _invalid(SEED_JOBS_FILE, error) from None
    try:
        applications = SeedApplications.model_validate(
            _read_json(data_dir / SEED_APPLICATIONS_FILE)
        ).root
    except ValueError as error:
        raise _invalid(SEED_APPLICATIONS_FILE, error) from None
    job_ids = {job.external_id for job in jobs}
    unknown = sorted({app.job_external_id for app in applications} - job_ids)
    if unknown:
        raise SeedDataError(f"{SEED_APPLICATIONS_FILE}: unknown job_external_id {unknown}")
    return SeedData(profile, tuple(jobs), tuple(applications))


def seed_application_create(item: SeedApplication, job_id: int, today: date) -> ApplicationCreate:
    """The application to create for `item`, with relative dates resolved against `today`."""
    interview_date = None
    if item.interview_in_days is not None:
        interview_day = today + timedelta(days=item.interview_in_days)
        interview_date = datetime.combine(interview_day, SEED_INTERVIEW_TIME)
    return ApplicationCreate(
        job_id=job_id,
        status=item.status,
        notes=item.notes,
        applied_at=(
            None if item.applied_days_ago is None else today - timedelta(days=item.applied_days_ago)
        ),
        deadline=(
            None if item.deadline_in_days is None else today + timedelta(days=item.deadline_in_days)
        ),
        interview_date=interview_date,
        recruiter_name=item.recruiter_name,
        recruiter_email=item.recruiter_email,
        outcome=item.outcome,
    )


def require_demo_user(session: Session) -> User:
    """The seeded demo user, or `DemoUserNotSeededError` (used by `app.cli ingest`)."""
    user = UserRepository(session).get_by_seed_key(DEMO_SEED_KEY)
    if user is None:
        raise DemoUserNotSeededError
    return user


class SeedService:
    """Runs the seed as one unit of work (one commit, rollback on any failure)."""

    def __init__(self, session: Session, clock: Clock, settings: Settings) -> None:
        self._session = session
        self._clock = clock
        self._settings = settings
        self._users = UserRepository(session)
        self._skills = SkillRepository(session)
        self._jobs = JobRepository(session)
        self._profiles = ProfileService(session, clock)
        self._application_service = ApplicationService(session, clock)
        self._ingestion = IngestionService(session, clock, default_sources(settings))

    def run(self) -> SeedSummary:
        """Seed the demo dataset; safe to run any number of times (R11.2).

        Raises `SeedDataError` for invalid seed files and `EmailTakenError` when
        `DEMO_USER_EMAIL` belongs to another user; nothing is written in either case.
        """
        data = load_seed_data(
            self._settings.data_dir,
            self._settings.demo_user_name,
            str(self._settings.demo_user_email),
        )
        try:
            skills_created = self._upsert_skills(data.skill_names())
            user, user_created = self._ensure_demo_user(data.profile)
            jobs = self._ingestion.stage_batches(user, [self._job_batch(data.jobs)])
            if jobs.rejected:
                raise SeedDataError(
                    f"{SEED_JOBS_FILE}: {jobs.rejected} job(s) rejected",
                    details={"errors": [error.model_dump() for error in jobs.errors]},
                )
            applications_created = 0
            if user_created:
                applications_created = self._seed_applications(user, data.applications)
            applications_skipped = len(data.applications) - applications_created
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        summary = SeedSummary(
            user_created=user_created,
            skills_created=skills_created,
            jobs_created=jobs.created,
            jobs_updated=jobs.updated,
            jobs_duplicates=jobs.duplicates,
            applications_created=applications_created,
            applications_skipped=applications_skipped,
        )
        logger.info(
            "Seed complete: user_created=%s skills_created=%d jobs_created=%d jobs_updated=%d "
            "jobs_duplicates=%d applications_created=%d applications_skipped=%d",
            summary.user_created,
            summary.skills_created,
            summary.jobs_created,
            summary.jobs_updated,
            summary.jobs_duplicates,
            summary.applications_created,
            summary.applications_skipped,
        )
        return summary

    def _upsert_skills(self, names: frozenset[str]) -> int:
        """Ensure every name exists in the catalog; return how many were inserted."""
        existing = self._skills.get_by_normalized_names(names)
        self._skills.get_or_create_many({name: display_skill(name) for name in names})
        return len(names) - len(existing)

    def _ensure_demo_user(self, profile: ProfileUpdate) -> tuple[User, bool]:
        """The `seed_key='demo'` user; created from the seed profile only when missing, and
        never modified when present, even if its email or profile was edited (R11.2)."""
        user = self._users.get_by_seed_key(DEMO_SEED_KEY)
        if user is not None:
            return user, False
        if self._users.get_by_email(profile.email) is not None:
            raise EmailTakenError(EMAIL_CONFLICT_MESSAGE)
        now = self._clock.now()
        user = self._users.add(
            User(
                seed_key=DEMO_SEED_KEY,
                name=profile.name,
                email=profile.email,
                created_at=now,
                updated_at=now,
            )
        )
        self._profiles.apply(user, profile)
        return user, True

    @staticmethod
    def _job_batch(jobs: tuple[SeedJob, ...]) -> RawBatch:
        """Seed jobs in the normalized format, stored with `source='seed'` (§11.2)."""
        items: list[object] = [job.model_dump(mode="json", exclude_none=True) for job in jobs]
        return RawBatch(RawFormat.NORMALIZED, JobSource.SEED, items)

    def _seed_applications(self, user: User, applications: tuple[SeedApplication, ...]) -> int:
        """Insert the seed applications for a just-created demo user; return how many.

        Called only in the run that creates the user, so later runs never re-create an
        application the user deleted or touch one they changed (R11.2, §12). A new user has no
        applications and the file has one per job, so `UNIQUE(user_id, job_id)` always holds.
        """
        today = self._clock.today()
        created = 0
        for item in applications:
            job = self._jobs.get_by_source_external_id(JobSource.SEED.value, item.job_external_id)
            if job is None:
                # Only possible when the seed job was skipped as a duplicate of another job.
                logger.warning("Seed job %s not found; application skipped", item.job_external_id)
                continue
            self._application_service.insert(
                user, job, seed_application_create(item, job.id, today)
            )
            created += 1
        return created
