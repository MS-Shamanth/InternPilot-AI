"""Job discovery API contract (R2, design.md §8, §8.1, §8.3).

`JobListParams` is the validated query string of `GET /api/jobs`; `JobSummary`, `JobDetail`,
`JobState` and `Page[T]` are responses.
"""

from collections.abc import Mapping
from datetime import date
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field, StringConstraints, field_validator

from app.schemas.application import Application
from app.schemas.common import (
    EducationLevel,
    EmploymentType,
    ExperienceLevel,
    JobSource,
    RequestModel,
    SalaryPeriod,
    UtcDateTime,
    WorkMode,
    blank_to_none,
)
from app.schemas.match import MatchExplanation
from app.services.application_status import ApplicationStatus
from app.services.matching.normalization import normalize_skill

QUERY_MAX_LENGTH = 100
LOCATION_FILTER_MAX_LENGTH = 120
SKILLS_FILTER_MAX_ITEMS = 10
SKILLS_FILTER_MAX_LENGTH = 600
SKILLS_SEPARATOR = ","
PAGE_SIZE_DEFAULT = 20
PAGE_SIZE_MAX = 100
SCORE_MIN = 0
SCORE_MAX = 100


class JobSortKey(StrEnum):
    MATCH_SCORE = "match_score"
    DISCOVERED_AT = "discovered_at"
    DEADLINE = "deadline"
    TITLE = "title"
    COMPANY = "company"
    SALARY = "salary"


class SortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"


# Order used when the client sends `sort` without `order` (design.md §8 sort semantics).
DEFAULT_SORT_ORDER: Mapping[JobSortKey, SortOrder] = MappingProxyType(
    {
        JobSortKey.MATCH_SCORE: SortOrder.DESC,
        JobSortKey.DISCOVERED_AT: SortOrder.DESC,
        JobSortKey.DEADLINE: SortOrder.ASC,
        JobSortKey.TITLE: SortOrder.ASC,
        JobSortKey.COMPANY: SortOrder.ASC,
        JobSortKey.SALARY: SortOrder.DESC,
    }
)

SearchText = Annotated[
    Annotated[str, StringConstraints(strip_whitespace=True, max_length=QUERY_MAX_LENGTH)] | None,
    BeforeValidator(blank_to_none),
]
LocationFilter = Annotated[
    Annotated[str, StringConstraints(strip_whitespace=True, max_length=LOCATION_FILTER_MAX_LENGTH)]
    | None,
    BeforeValidator(blank_to_none),
]


class JobListParams(RequestModel):
    """Query parameters of `GET /api/jobs` (R2.3-R2.6, R2.13).

    Unknown parameters are rejected. `skills` is a comma-separated list; it is stored
    canonically (normalized, de-duplicated, sorted) and read through `skill_names`.
    """

    q: SearchText = None
    employment_type: list[EmploymentType] = Field(default_factory=list)
    work_mode: list[WorkMode] = Field(default_factory=list)
    experience_level: list[ExperienceLevel] = Field(default_factory=list)
    location: LocationFilter = None
    source: JobSource | None = None
    skills: Annotated[str | None, Field(max_length=SKILLS_FILTER_MAX_LENGTH)] = None
    min_score: Annotated[int | None, Field(ge=SCORE_MIN, le=SCORE_MAX)] = None
    bookmarked: bool = False
    include_hidden: bool = False
    sort: JobSortKey = JobSortKey.MATCH_SCORE
    order: SortOrder | None = None
    page: Annotated[int, Field(ge=1)] = 1
    page_size: Annotated[int, Field(ge=1, le=PAGE_SIZE_MAX)] = PAGE_SIZE_DEFAULT

    @field_validator("skills")
    @classmethod
    def _canonical_skills(cls, value: str | None) -> str | None:
        """Normalize each entry; empty entries are ignored, unusable ones are rejected."""
        if value is None:
            return None
        names: set[str] = set()
        for entry in value.split(SKILLS_SEPARATOR):
            if not entry.strip():
                continue
            name = normalize_skill(entry)
            if name is None:
                raise ValueError("Each skill must contain at least one letter, digit or symbol")
            names.add(name)
        if len(names) > SKILLS_FILTER_MAX_ITEMS:
            raise ValueError(f"At most {SKILLS_FILTER_MAX_ITEMS} skills may be given")
        return SKILLS_SEPARATOR.join(sorted(names)) or None

    @property
    def skill_names(self) -> tuple[str, ...]:
        """Normalized skill names to filter by (empty when no skill filter is set)."""
        return tuple(self.skills.split(SKILLS_SEPARATOR)) if self.skills else ()

    @property
    def effective_order(self) -> SortOrder:
        return self.order or DEFAULT_SORT_ORDER[self.sort]


class JobState(BaseModel):
    """The user's flags for one job (R2.8, R2.9)."""

    job_id: int
    is_bookmarked: bool
    is_hidden: bool


class JobSummary(BaseModel):
    """One job in a list (design.md §8, §8.3); skills are display names sorted by normalized name.

    `match_score` is the engine score against the live profile (R2.2, R3.12).
    """

    id: int
    title: str
    company: str
    location: str
    employment_type: EmploymentType
    work_mode: WorkMode
    experience_level: ExperienceLevel | None
    salary_min: int | None
    salary_max: int | None
    salary_currency: str | None
    salary_period: SalaryPeriod | None
    deadline: date | None
    source: JobSource
    discovered_at: UtcDateTime
    required_skills: list[str]
    preferred_skills: list[str]
    is_bookmarked: bool
    is_hidden: bool
    application_status: ApplicationStatus | None
    match_score: int


class JobDetail(JobSummary):
    """A single job with the user's application and match explanation (design.md §8.3)."""

    match_explanation: MatchExplanation
    description: str
    application_url: str
    min_education_level: EducationLevel | None
    application: Application | None


class Page[T](BaseModel):
    """A page of a paginated list; `total_pages` is 0 when `total` is 0."""

    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int


class Recommendation(BaseModel):
    """A recommended job with its full match explanation (R7.1, design.md §7)."""

    job: JobSummary
    match_explanation: MatchExplanation
