"""Seed file contracts (R11.1-R11.3, design.md §12).

The three files in `DATA_DIR` are validated strictly before anything is written: unknown keys
are rejected and every date is relative (`*_in_days`, `applied_days_ago`) so a demo started on
any day has meaningful upcoming deadlines (R11.3).
"""

from typing import Annotated, Self

from pydantic import AfterValidator, Field, RootModel, StringConstraints, model_validator

from app.schemas.application import Notes, Outcome, RecruiterEmail, RecruiterName
from app.schemas.common import (
    EducationLevel,
    EmploymentType,
    ExperienceLevel,
    RequestModel,
    SalaryPeriod,
    WorkMode,
    validate_http_url,
)
from app.schemas.ingest import (
    APPLICATION_URL_MAX_LENGTH,
    DESCRIPTION_MAX_LENGTH,
    EXTERNAL_ID_MAX_LENGTH,
    JobText,
    SkillList,
)
from app.schemas.profile import ProfileUpdate
from app.services.application_status import SUBMITTED_STATUSES, ApplicationStatus

RELATIVE_DAYS_MAX = 365
# Name and email of the demo user come from `DEMO_USER_NAME` / `DEMO_USER_EMAIL` (§12, §13.1).
PROFILE_IDENTITY_FIELDS = ("name", "email")
# Statuses that may carry an application date: the submitted ones plus `Withdrawn` (§7).
DATED_STATUSES = SUBMITTED_STATUSES | {ApplicationStatus.WITHDRAWN}

RelativeDays = Annotated[int, Field(strict=True, ge=-RELATIVE_DAYS_MAX, le=RELATIVE_DAYS_MAX)]
DaysAgo = Annotated[int, Field(strict=True, ge=0, le=RELATIVE_DAYS_MAX)]
ExternalId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=EXTERNAL_ID_MAX_LENGTH),
]
Salary = Annotated[int, Field(strict=True, ge=0)]


class SeedJob(RequestModel):
    """One `seed_jobs.json` item: the normalized ingestion format (§11.3) with a relative
    `deadline_in_days` (null = no deadline). Skills hold normalized names after validation."""

    external_id: ExternalId
    title: JobText
    company: JobText
    location: JobText
    employment_type: EmploymentType
    work_mode: WorkMode
    experience_level: ExperienceLevel | None = None
    min_education_level: EducationLevel | None = None
    description: Annotated[str, Field(max_length=DESCRIPTION_MAX_LENGTH)] = ""
    salary_min: Salary | None = None
    salary_max: Salary | None = None
    salary_currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")] | None = None
    salary_period: SalaryPeriod | None = None
    application_url: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True, min_length=1, max_length=APPLICATION_URL_MAX_LENGTH
        ),
        AfterValidator(validate_http_url),
    ]
    deadline_in_days: RelativeDays | None = None
    required_skills: SkillList = Field(default_factory=list)
    preferred_skills: SkillList = Field(default_factory=list)


class SeedJobs(RootModel[list[SeedJob]]):
    """`seed_jobs.json`: a JSON list of jobs with unique `external_id`s."""

    @model_validator(mode="after")
    def _unique_external_ids(self) -> Self:
        ids = [job.external_id for job in self.root]
        if len(set(ids)) != len(ids):
            raise ValueError("external_id values must be unique")
        return self


class SeedApplication(RequestModel):
    """One `seed_applications.json` item, keyed by the seed job's `external_id`.

    Dates are relative to the seed day: `applied_days_ago` (required for submitted statuses,
    allowed for `Withdrawn`, forbidden for `Saved`/`Interested`), `deadline_in_days` (overrides
    the job deadline) and `interview_in_days` (interview at 10:00 UTC that day).
    """

    job_external_id: ExternalId
    status: ApplicationStatus
    applied_days_ago: DaysAgo | None = None
    deadline_in_days: RelativeDays | None = None
    interview_in_days: RelativeDays | None = None
    recruiter_name: RecruiterName = None
    recruiter_email: RecruiterEmail = None
    notes: Notes = ""
    outcome: Outcome = None

    @model_validator(mode="after")
    def _applied_date_matches_status(self) -> Self:
        if self.status in SUBMITTED_STATUSES and self.applied_days_ago is None:
            raise ValueError(f"applied_days_ago is required for status {self.status.value}")
        if self.status not in DATED_STATUSES and self.applied_days_ago is not None:
            raise ValueError(f"applied_days_ago is not allowed for status {self.status.value}")
        return self


class SeedApplications(RootModel[list[SeedApplication]]):
    """`seed_applications.json`: a JSON list with at most one application per job."""

    @model_validator(mode="after")
    def _one_application_per_job(self) -> Self:
        ids = [application.job_external_id for application in self.root]
        if len(set(ids)) != len(ids):
            raise ValueError("job_external_id values must be unique")
        return self


def parse_seed_profile(raw: object, name: str, email: str) -> ProfileUpdate:
    """Validate `seed_profile.json` as a full profile whose name and email are the configured
    demo identity; the file itself must not contain `name` or `email`.

    Raises `ValueError` (including Pydantic's `ValidationError`) when the file is invalid.
    """
    if not isinstance(raw, dict):
        raise ValueError("seed profile must be a JSON object")
    present = sorted(set(PROFILE_IDENTITY_FIELDS) & set(raw))
    if present:
        raise ValueError(f"seed profile must not set {', '.join(present)}")
    return ProfileUpdate.model_validate({**raw, "name": name, "email": email})
