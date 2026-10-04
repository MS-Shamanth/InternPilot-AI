"""Application tracker API contract (R5, design.md §8, §8.1, §8.3).

`ApplicationCreate` and `ApplicationUpdate` are request bodies; `Application` and
`ApplicationsMeta` are responses. `ApplicationUpdate` is a partial update: only the fields
present in the request (`model_fields_set`) are applied, and an explicit `null` clears a
nullable field.
"""

from datetime import UTC, date, datetime
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    field_validator,
)

from app.schemas.common import RequestModel, UtcDateTime, blank_to_none
from app.services.application_status import ApplicationStatus

NOTES_MAX_LENGTH = 5000
RECRUITER_NAME_MAX_LENGTH = 120
RECRUITER_EMAIL_MAX_LENGTH = 254
OUTCOME_MAX_LENGTH = 500

# Fields that a PATCH may change besides `status` (R5.7).
EDITABLE_FIELDS: tuple[str, ...] = (
    "notes",
    "applied_at",
    "deadline",
    "interview_date",
    "recruiter_name",
    "recruiter_email",
    "outcome",
)


def _as_utc(value: datetime) -> datetime:
    """Naive timestamps are assumed to be UTC; aware ones are converted to UTC (§8.1)."""
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _lowercase(value: str) -> str:
    return value.lower()


Notes = Annotated[str, Field(max_length=NOTES_MAX_LENGTH)]
RecruiterName = Annotated[
    Annotated[str, StringConstraints(strip_whitespace=True, max_length=RECRUITER_NAME_MAX_LENGTH)]
    | None,
    BeforeValidator(blank_to_none),
]
RecruiterEmail = Annotated[
    Annotated[EmailStr, Field(max_length=RECRUITER_EMAIL_MAX_LENGTH), AfterValidator(_lowercase)]
    | None,
    BeforeValidator(blank_to_none),
]
Outcome = Annotated[
    Annotated[str, StringConstraints(strip_whitespace=True, max_length=OUTCOME_MAX_LENGTH)] | None,
    BeforeValidator(blank_to_none),
]
InterviewDate = Annotated[datetime, AfterValidator(_as_utc)]


class ApplicationCreate(RequestModel):
    """`POST /api/applications`: any status may be used on create (past applications)."""

    job_id: Annotated[int, Field(ge=1)]
    status: ApplicationStatus = ApplicationStatus.SAVED
    notes: Notes = ""
    applied_at: date | None = None
    deadline: date | None = None
    interview_date: InterviewDate | None = None
    recruiter_name: RecruiterName = None
    recruiter_email: RecruiterEmail = None
    outcome: Outcome = None


class ApplicationUpdate(RequestModel):
    """`PATCH /api/applications/{id}`: omitted fields are untouched, `null` clears.

    `status` and `notes` are not nullable, so an explicit `null` for them is rejected.
    """

    status: ApplicationStatus | None = None
    notes: Notes | None = None
    applied_at: date | None = None
    deadline: date | None = None
    interview_date: InterviewDate | None = None
    recruiter_name: RecruiterName = None
    recruiter_email: RecruiterEmail = None
    outcome: Outcome = None

    @field_validator("status", "notes", mode="before")
    @classmethod
    def _reject_explicit_null(cls, value: object) -> object:
        # Runs only for values present in the request (defaults are not validated).
        if value is None:
            raise ValueError("Field cannot be null")
        return value


class ApplicationJob(BaseModel):
    """The job summary embedded in every application (R5.9)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    company: str
    location: str
    deadline: date | None


class Application(BaseModel):
    """A tracker record with its job summary (design.md §8.3)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    status: ApplicationStatus
    applied_at: date | None
    deadline: date | None
    interview_date: UtcDateTime | None
    recruiter_name: str | None
    recruiter_email: str | None
    notes: str
    outcome: str | None
    created_at: UtcDateTime
    updated_at: UtcDateTime
    job: ApplicationJob


class ApplicationsMeta(BaseModel):
    """Statuses and allowed moves, both in canonical order (R5.10)."""

    statuses: list[ApplicationStatus]
    transitions: dict[ApplicationStatus, list[ApplicationStatus]]
