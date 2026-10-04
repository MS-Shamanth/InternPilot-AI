"""Job ingestion contract (R10, design.md §11.1, §11.3, §8.3).

`IngestRequest` is the body of `POST /api/jobs/ingest`; `IngestResult` its response. `JobCreate`
is the validated shape of one normalized job, produced by `services/ingestion/normalizers.py`
before anything is written.
"""

from datetime import date
from enum import StrEnum
from typing import Annotated, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
    ValidationInfo,
    field_validator,
    model_validator,
)

from app.schemas.common import (
    EducationLevel,
    EmploymentType,
    ExperienceLevel,
    JobSource,
    RequestModel,
    SalaryPeriod,
    WorkMode,
    validate_http_url,
)
from app.services.matching.normalization import normalize_skill

INGEST_LIMIT_DEFAULT = 100
INGEST_MAX_ITEMS = 500
INGEST_MAX_ERRORS = 50
JOB_TEXT_MAX_LENGTH = 200
EXTERNAL_ID_MAX_LENGTH = 128
DESCRIPTION_MAX_LENGTH = 20_000
APPLICATION_URL_MAX_LENGTH = 500
JOB_SKILLS_MAX_ITEMS = 30
PAYLOAD_ITEM_KEYS = ("jobs", "data")


class IngestSourceName(StrEnum):
    """Sources a caller may request; `seed` is only ever a stored value (§11.2)."""

    FIXTURE = "fixture"
    REMOTIVE = "remotive"
    ARBEITNOW = "arbeitnow"
    PAYLOAD = "payload"


class RawFormat(StrEnum):
    """Shape of raw items: a public API's job object or the seed/normalized format (§12)."""

    REMOTIVE = "remotive"
    ARBEITNOW = "arbeitnow"
    NORMALIZED = "normalized"


def unwrap_items(payload: object) -> list[object] | None:
    """The item list of a payload: the list itself, or the `jobs`/`data` list of an object."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in PAYLOAD_ITEM_KEYS:
            items = payload.get(key)
            if isinstance(items, list):
                return items
    return None


class IngestRequest(RequestModel):
    """Body of `POST /api/jobs/ingest` (§11.1). `format`/`payload` only for `source=payload`."""

    source: IngestSourceName
    fallback: bool = True
    limit: Annotated[int, Field(ge=1, le=INGEST_MAX_ITEMS)] = INGEST_LIMIT_DEFAULT
    format: RawFormat | None = None
    payload: dict[str, JsonValue] | list[JsonValue] | None = None

    @model_validator(mode="after")
    def _payload_only_for_payload_source(self) -> Self:
        if self.source is not IngestSourceName.PAYLOAD:
            if self.format is not None or self.payload is not None:
                raise ValueError("format and payload are only allowed when source is 'payload'")
            return self
        if self.format is None or self.payload is None:
            raise ValueError("format and payload are required when source is 'payload'")
        items = unwrap_items(self.payload)
        if items is None:
            raise ValueError("payload must be a list or an object with a 'jobs' or 'data' list")
        if len(items) > INGEST_MAX_ITEMS:
            raise ValueError(f"payload may contain at most {INGEST_MAX_ITEMS} items")
        return self


def _normalize_skill_list(values: list[str]) -> list[str]:
    """Normalized names in first-seen order; every entry must normalize (§5.1)."""
    names: list[str] = []
    for value in values:
        name = normalize_skill(value)
        if name is None:
            raise ValueError("Each skill must be 1-50 characters after normalization")
        if name not in names:
            names.append(name)
    return names


JobText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=JOB_TEXT_MAX_LENGTH),
]
SkillList = Annotated[
    list[str], Field(max_length=JOB_SKILLS_MAX_ITEMS), AfterValidator(_normalize_skill_list)
]


class JobCreate(BaseModel):
    """One normalized, validated job ready to persist (§11.3).

    Skills hold normalized names; a skill that is also required is dropped from preferred.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    source: JobSource
    external_id: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=EXTERNAL_ID_MAX_LENGTH),
    ]
    title: JobText
    company: JobText
    location: JobText
    employment_type: EmploymentType
    work_mode: WorkMode
    experience_level: ExperienceLevel | None = None
    min_education_level: EducationLevel | None = None
    description: Annotated[str, Field(max_length=DESCRIPTION_MAX_LENGTH)] = ""
    salary_min: Annotated[int | None, Field(ge=0)] = None
    salary_max: Annotated[int | None, Field(ge=0)] = None
    salary_currency: Annotated[str | None, Field(pattern=r"^[A-Z]{3}$")] = None
    salary_period: SalaryPeriod | None = None
    application_url: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True, min_length=1, max_length=APPLICATION_URL_MAX_LENGTH
        ),
        AfterValidator(validate_http_url),
    ]
    deadline: date | None = None
    required_skills: SkillList = Field(default_factory=list)
    preferred_skills: SkillList = Field(default_factory=list)

    @field_validator("salary_min", "salary_max", mode="before")
    @classmethod
    def _reject_bool_salary(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("Salary must be a number")
        return value

    @field_validator("preferred_skills")
    @classmethod
    def _drop_required_from_preferred(cls, value: list[str], info: ValidationInfo) -> list[str]:
        """`required_skills` is declared first, so it is already validated here."""
        required = set(info.data.get("required_skills", []))
        return [name for name in value if name not in required]

    @model_validator(mode="after")
    def _check_salary_range(self) -> Self:
        if (
            self.salary_min is not None
            and self.salary_max is not None
            and self.salary_min > self.salary_max
        ):
            raise ValueError("salary_min must not exceed salary_max")
        return self


class IngestError(BaseModel):
    """One problem in a run: an item rejection (`index` set) or a source failure (`index` null)."""

    index: int | None
    reason: str


class IngestResult(BaseModel):
    """Outcome of one ingestion run (R10.8, §11.5); `errors` holds at most 50 entries."""

    requested_source: IngestSourceName
    source: IngestSourceName
    fallback_used: bool
    fetched: int
    created: int
    updated: int
    duplicates: int
    rejected: int
    errors: list[IngestError]
