"""Match explanation API contract (R4.1, R4.2, design.md §5.5, §8.3).

`MatchExplanation` mirrors the engine's `MatchResult` 1:1. The engine keeps exact `Fraction`
values; this boundary serializes `points` to 2 decimals and `ratio` to 4 decimals with the same
half-up rule the engine uses for the score, so JSON never suffers float tie errors.
"""

from pydantic import BaseModel

from app.services.matching.engine import to_rounded_float
from app.services.matching.types import FactorKey, FactorResult, MatchResult

POINTS_DECIMALS = 2
RATIO_DECIMALS = 4


class Factor(BaseModel):
    """One weighted factor of the score (design.md §5.3)."""

    key: FactorKey
    label: str
    weight: int
    points: float
    ratio: float
    detail: str


class MatchExplanation(BaseModel):
    """The `match_explanation` object (design.md §5.5); skill lists hold display names."""

    job_id: int
    score: int
    algorithm_version: str
    factors: list[Factor]
    matched_required_skills: list[str]
    missing_required_skills: list[str]
    matched_preferred_skills: list[str]
    missing_preferred_skills: list[str]
    positive_reasons: list[str]
    negative_reasons: list[str]


def factor_from_result(factor: FactorResult) -> Factor:
    return Factor(
        key=factor.key,
        label=factor.label,
        weight=factor.weight,
        points=to_rounded_float(factor.points, POINTS_DECIMALS),
        ratio=to_rounded_float(factor.ratio, RATIO_DECIMALS),
        detail=factor.detail,
    )


def match_explanation_from_result(result: MatchResult) -> MatchExplanation:
    """Convert an engine `MatchResult` into the API schema, preserving factor order."""
    return MatchExplanation(
        job_id=result.job_id,
        score=result.score,
        algorithm_version=result.algorithm_version,
        factors=[factor_from_result(factor) for factor in result.factors],
        matched_required_skills=list(result.matched_required_skills),
        missing_required_skills=list(result.missing_required_skills),
        matched_preferred_skills=list(result.matched_preferred_skills),
        missing_preferred_skills=list(result.missing_preferred_skills),
        positive_reasons=list(result.positive_reasons),
        negative_reasons=list(result.negative_reasons),
    )
