"""Value types for the matching engine (design.md §5, §5.5).

Everything here is a frozen dataclass or a `StrEnum` so the engine stays pure: it imports no
models, repositories or schemas. The level enums mirror the API enums in `app.schemas.common`
value-for-value; because they are `StrEnum`s, the services can pass either type and comparisons
and dictionary lookups work on the string value.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction
from types import MappingProxyType

ALGORITHM_VERSION = "1.0.0"


class WorkMode(StrEnum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"


class ExperienceLevel(StrEnum):
    INTERNSHIP = "internship"
    ENTRY = "entry"
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"


class EducationLevel(StrEnum):
    HIGH_SCHOOL = "high_school"
    DIPLOMA = "diploma"
    BACHELOR = "bachelor"
    MASTER = "master"
    PHD = "phd"


class FactorKey(StrEnum):
    """The eight factors, declared in engine order (design.md §5.3)."""

    REQUIRED_SKILLS = "required_skills"
    PREFERRED_SKILLS = "preferred_skills"
    ROLE_SIMILARITY = "role_similarity"
    EXPERIENCE = "experience"
    LOCATION = "location"
    WORK_MODE = "work_mode"
    EDUCATION = "education"
    PROJECTS = "projects"


@dataclass(frozen=True)
class FactorSpec:
    key: FactorKey
    label: str
    weight: int


FACTOR_SPECS: tuple[FactorSpec, ...] = (
    FactorSpec(FactorKey.REQUIRED_SKILLS, "Required skills", 35),
    FactorSpec(FactorKey.PREFERRED_SKILLS, "Preferred skills", 10),
    FactorSpec(FactorKey.ROLE_SIMILARITY, "Role similarity", 15),
    FactorSpec(FactorKey.EXPERIENCE, "Experience", 15),
    FactorSpec(FactorKey.LOCATION, "Location", 10),
    FactorSpec(FactorKey.WORK_MODE, "Work mode", 5),
    FactorSpec(FactorKey.EDUCATION, "Education", 5),
    FactorSpec(FactorKey.PROJECTS, "Project relevance", 5),
)
FACTOR_WEIGHTS: Mapping[FactorKey, int] = MappingProxyType(
    {spec.key: spec.weight for spec in FACTOR_SPECS}
)
MAX_SCORE = 100
MIN_SCORE = 0


@dataclass(frozen=True)
class ProjectInput:
    name: str
    technologies: tuple[str, ...]


@dataclass(frozen=True)
class MatchProfile:
    """Profile side of a match. Strings are raw; the engine normalizes them."""

    technical_skills: tuple[str, ...] = ()
    target_roles: tuple[str, ...] = ()
    location: str | None = None
    preferred_locations: tuple[str, ...] = ()
    preferred_work_modes: tuple[WorkMode, ...] = ()
    experience_level: ExperienceLevel | None = None
    education_level: EducationLevel | None = None
    projects: tuple[ProjectInput, ...] = ()


@dataclass(frozen=True)
class MatchJob:
    """Job side of a match. Skill strings are raw; the engine normalizes them."""

    id: int
    title: str
    location: str
    work_mode: WorkMode
    experience_level: ExperienceLevel | None = None
    min_education_level: EducationLevel | None = None
    required_skills: tuple[str, ...] = ()
    preferred_skills: tuple[str, ...] = ()


@dataclass(frozen=True)
class FactorResult:
    """One weighted factor. `points == weight * ratio` exactly (R4.2)."""

    key: FactorKey
    label: str
    weight: int
    ratio: Fraction
    points: Fraction
    detail: str


@dataclass(frozen=True)
class MatchResult:
    """The `match_explanation` (design.md §5.5); skill lists hold display names."""

    job_id: int
    score: int
    algorithm_version: str
    factors: tuple[FactorResult, ...]
    matched_required_skills: tuple[str, ...]
    missing_required_skills: tuple[str, ...]
    matched_preferred_skills: tuple[str, ...]
    missing_preferred_skills: tuple[str, ...]
    positive_reasons: tuple[str, ...]
    negative_reasons: tuple[str, ...]

    @property
    def total_points(self) -> Fraction:
        """Exact unrounded sum of factor points."""
        return sum((factor.points for factor in self.factors), Fraction(0))
