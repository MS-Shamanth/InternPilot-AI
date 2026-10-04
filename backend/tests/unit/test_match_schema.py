"""`MatchExplanation` schema and converter (R4.1, R4.2; design.md §5.5, §8.3)."""

from dataclasses import replace
from fractions import Fraction

from app.schemas.match import factor_from_result, match_explanation_from_result
from app.services.matching import (
    FACTOR_SPECS,
    FactorKey,
    MatchJob,
    MatchProfile,
    WorkMode,
    compute_match,
)

EXPECTED_KEYS = {
    "job_id",
    "score",
    "algorithm_version",
    "factors",
    "matched_required_skills",
    "missing_required_skills",
    "matched_preferred_skills",
    "missing_preferred_skills",
    "positive_reasons",
    "negative_reasons",
}
EXPECTED_FACTOR_KEYS = {"key", "label", "weight", "points", "ratio", "detail"}

PROFILE = MatchProfile(technical_skills=("Python", "React", "SQL"))
JOB = MatchJob(
    id=12,
    title="Software Engineer",
    location="Berlin, Germany",
    work_mode=WorkMode.ONSITE,
    required_skills=("Python", "React", "SQL", "Java"),
)


def test_match_explanation_dump_has_design_shape() -> None:
    result = compute_match(PROFILE, JOB)
    dumped = match_explanation_from_result(result).model_dump(mode="json")
    assert set(dumped) == EXPECTED_KEYS
    assert dumped["job_id"] == 12
    assert dumped["score"] == result.score
    assert [factor["key"] for factor in dumped["factors"]] == [
        spec.key.value for spec in FACTOR_SPECS
    ]
    assert all(set(factor) == EXPECTED_FACTOR_KEYS for factor in dumped["factors"])
    required = dumped["factors"][0]
    assert required == {
        "key": "required_skills",
        "label": "Required skills",
        "weight": 35,
        "points": 26.25,
        "ratio": 0.75,
        "detail": "3 of 4 required skills matched",
    }
    assert dumped["missing_required_skills"] == ["Java"]
    assert dumped["negative_reasons"][0] == "Java experience is missing (required)"


def test_factor_rounds_points_to_two_and_ratio_to_four_decimals_half_up() -> None:
    base = compute_match(PROFILE, JOB).factors[0]
    # ratio 1/3 -> 0.3333; points 35 * 1/3 = 11.666... -> 11.67
    third = factor_from_result(replace(base, ratio=Fraction(1, 3), points=Fraction(35, 3)))
    assert (third.points, third.ratio) == (11.67, 0.3333)
    # exact ties round up: 0.125 -> 0.13 (points), 0.00005 -> 0.0001 (ratio)
    tie = factor_from_result(replace(base, ratio=Fraction(1, 20000), points=Fraction(1, 8)))
    assert (tie.points, tie.ratio) == (0.13, 0.0001)
    assert tie.key is FactorKey.REQUIRED_SKILLS
