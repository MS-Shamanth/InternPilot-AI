"""Deterministic matching engine and skill normalization (design.md §5)."""

from app.services.matching.engine import (
    clamp_score,
    compute_match,
    location_segments,
    role_tokens,
    round_half_up,
    to_rounded_float,
)
from app.services.matching.normalization import display_skill, normalize_skill, normalize_skills
from app.services.matching.types import (
    ALGORITHM_VERSION,
    FACTOR_SPECS,
    FACTOR_WEIGHTS,
    EducationLevel,
    ExperienceLevel,
    FactorKey,
    FactorResult,
    FactorSpec,
    MatchJob,
    MatchProfile,
    MatchResult,
    ProjectInput,
    WorkMode,
)

__all__ = [
    "ALGORITHM_VERSION",
    "FACTOR_SPECS",
    "FACTOR_WEIGHTS",
    "EducationLevel",
    "ExperienceLevel",
    "FactorKey",
    "FactorResult",
    "FactorSpec",
    "MatchJob",
    "MatchProfile",
    "MatchResult",
    "ProjectInput",
    "WorkMode",
    "clamp_score",
    "compute_match",
    "display_skill",
    "location_segments",
    "normalize_skill",
    "normalize_skills",
    "role_tokens",
    "round_half_up",
    "to_rounded_float",
]
