"""Profile API contract: `ProfileUpdate` (full replace) and `Profile` (R1, design.md §8.1, §8.3)."""

from typing import Annotated, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    EmailStr,
    Field,
    StringConstraints,
    model_validator,
)

from app.schemas.common import (
    EducationLevel,
    ExperienceLevel,
    HttpUrl,
    OptionalHttpUrl,
    RequestModel,
    UtcDateTime,
    WorkMode,
    blank_to_none,
    dedupe_casefold,
    require_host,
    require_unique,
)
from app.services.matching.normalization import normalize_skill

GITHUB_HOSTS = frozenset({"github.com", "www.github.com"})
LINKEDIN_HOSTS = frozenset({"linkedin.com", "www.linkedin.com"})
MIN_YEAR = 1950
MAX_YEAR = 2100


def _text(min_length: int, max_length: int) -> StringConstraints:
    return StringConstraints(strip_whitespace=True, min_length=min_length, max_length=max_length)


def _require_normalizable_skill(value: str) -> str:
    """R1.3: a skill that normalizes to nothing (e.g. only punctuation) is rejected, not dropped."""
    if normalize_skill(value) is None:
        raise ValueError("Skill must contain at least one letter, digit or symbol")
    return value


def _lowercase(value: str) -> str:
    return value.lower()


Year = Annotated[int, Field(ge=MIN_YEAR, le=MAX_YEAR)]
ProfileName = Annotated[str, _text(1, 100)]
ProfileEmail = Annotated[EmailStr, AfterValidator(_lowercase)]
OptionalLocation = Annotated[Annotated[str, _text(1, 120)] | None, BeforeValidator(blank_to_none)]
ShortListItem = Annotated[str, _text(1, 80)]
ShortList = Annotated[list[ShortListItem], Field(max_length=10), AfterValidator(dedupe_casefold)]
WorkModeList = Annotated[list[WorkMode], AfterValidator(require_unique)]
TechnicalSkill = Annotated[str, _text(1, 50), AfterValidator(_require_normalizable_skill)]
SkillName = Annotated[str, _text(1, 50)]
GithubUrl = Annotated[
    Annotated[HttpUrl, AfterValidator(require_host(GITHUB_HOSTS))] | None,
    BeforeValidator(blank_to_none),
]
LinkedinUrl = Annotated[
    Annotated[HttpUrl, AfterValidator(require_host(LINKEDIN_HOSTS))] | None,
    BeforeValidator(blank_to_none),
]
OptionalText100 = Annotated[Annotated[str, _text(1, 100)] | None, BeforeValidator(blank_to_none)]
OptionalText120 = Annotated[Annotated[str, _text(1, 120)] | None, BeforeValidator(blank_to_none)]


class EducationEntry(RequestModel):
    institution: Annotated[str, _text(1, 150)]
    degree: OptionalText100 = None
    field: OptionalText100 = None
    start_year: Year | None = None
    end_year: Year | None = None

    @model_validator(mode="after")
    def _check_year_order(self) -> Self:
        if (
            self.start_year is not None
            and self.end_year is not None
            and self.start_year > self.end_year
        ):
            raise ValueError("start_year must not be after end_year")
        return self


class Project(RequestModel):
    name: Annotated[str, _text(1, 120)]
    description: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] = ""
    technologies: Annotated[list[SkillName], Field(max_length=20)] = Field(default_factory=list)
    url: OptionalHttpUrl = None


class Certification(RequestModel):
    name: Annotated[str, _text(1, 120)]
    issuer: OptionalText120 = None
    year: Year | None = None


class ProfileUpdate(RequestModel):
    """Full replace of the profile: omitted optional fields reset to empty/null."""

    name: ProfileName
    email: ProfileEmail
    location: OptionalLocation = None
    target_roles: ShortList = Field(default_factory=list)
    preferred_locations: ShortList = Field(default_factory=list)
    preferred_work_modes: WorkModeList = Field(default_factory=list)
    experience_level: ExperienceLevel | None = None
    education_level: EducationLevel | None = None
    education: Annotated[list[EducationEntry], Field(max_length=10)] = Field(default_factory=list)
    technical_skills: Annotated[list[TechnicalSkill], Field(max_length=100)] = Field(
        default_factory=list
    )
    soft_skills: Annotated[list[SkillName], Field(max_length=50)] = Field(default_factory=list)
    projects: Annotated[list[Project], Field(max_length=20)] = Field(default_factory=list)
    certifications: Annotated[list[Certification], Field(max_length=30)] = Field(
        default_factory=list
    )
    resume_text: Annotated[str, Field(max_length=50_000)] = ""
    github_url: GithubUrl = None
    portfolio_url: OptionalHttpUrl = None
    linkedin_url: LinkedinUrl = None


class Profile(BaseModel):
    """`GET/PUT /api/profile` response; `technical_skills` are display names by normalized name."""

    id: int
    name: str
    email: str
    location: str | None
    target_roles: list[str]
    preferred_locations: list[str]
    preferred_work_modes: list[WorkMode]
    experience_level: ExperienceLevel | None
    education_level: EducationLevel | None
    education: list[EducationEntry]
    technical_skills: list[str]
    soft_skills: list[str]
    projects: list[Project]
    certifications: list[Certification]
    resume_text: str
    github_url: str | None
    portfolio_url: str | None
    linkedin_url: str | None
    created_at: UtcDateTime
    updated_at: UtcDateTime
