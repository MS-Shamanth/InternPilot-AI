"""Matching engine properties P1-P5 (design.md §17). Profile: tests/conftest.py."""

import math
from dataclasses import replace
from fractions import Fraction

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from app.services.matching import compute_match, normalize_skill
from app.services.matching.normalization import display_skill, normalize_skills
from app.services.matching.types import (
    FACTOR_SPECS,
    FactorKey,
    MatchJob,
    MatchProfile,
    MatchResult,
)
from tests.property.strategies import (
    jobs,
    permuted_job,
    permuted_profile,
    profiles,
    realistic_skills,
    skill_texts,
    skill_variants,
)

pytestmark = pytest.mark.property


def _factor_points(result: MatchResult, key: FactorKey) -> Fraction:
    return next(factor.points for factor in result.factors if factor.key == key)


@given(profiles, jobs)
def test_p1_score_is_bounded(profile: MatchProfile, job: MatchJob) -> None:
    """P1 — R3.1, R3.3, R3.4, R4.1, R4.2: the score is an int in 0..100 built from 8 factors.

    **Validates: Requirements 3.1, 3.3, 3.4, 4.1, 4.2**
    """
    result = compute_match(profile, job)

    assert isinstance(result.score, int)
    assert 0 <= result.score <= 100
    assert [factor.key for factor in result.factors] == [spec.key for spec in FACTOR_SPECS]
    for factor in result.factors:
        assert 0 <= factor.ratio <= 1
        assert 0 <= factor.points <= factor.weight
        assert factor.points == factor.weight * factor.ratio
    assert result.score == math.floor(result.total_points + Fraction(1, 2))


@given(profiles, jobs, st.data())
def test_p2_adding_matching_skill_never_lowers_score(
    profile: MatchProfile, job: MatchJob, data: st.DataObject
) -> None:
    """P2 — R3.5, R3.6: adding a skill the job lists never lowers the score.

    **Validates: Requirements 3.5, 3.6**
    """
    listed = job.required_skills + job.preferred_skills
    assume(listed)
    skill = data.draw(st.sampled_from(listed))
    extended = replace(profile, technical_skills=(*profile.technical_skills, skill))

    assert compute_match(extended, job).score >= compute_match(profile, job).score


@given(profiles, jobs, skill_texts)
def test_p2_adding_unrelated_skill_changes_nothing(
    profile: MatchProfile, job: MatchJob, skill: str
) -> None:
    """P2 — R3.5, R3.6: a skill the job does not list leaves the whole result unchanged.

    **Validates: Requirements 3.5, 3.6**
    """
    assume(
        normalize_skill(skill) not in normalize_skills(job.required_skills + job.preferred_skills)
    )
    extended = replace(profile, technical_skills=(*profile.technical_skills, skill))

    assert compute_match(extended, job) == compute_match(profile, job)


@given(profiles, jobs, st.lists(realistic_skills, max_size=8).map(tuple), st.data())
def test_p3_duplicate_skills_have_no_impact(
    profile: MatchProfile, job: MatchJob, skills: tuple[str, ...], data: st.DataObject
) -> None:
    """P3 — R3.2, R3.7: duplicates, case/space/edge-punctuation variants and aliases are no-ops.

    **Validates: Requirements 3.2, 3.7**
    """
    base = replace(profile, technical_skills=skills)
    variant = replace(profile, technical_skills=data.draw(skill_variants(skills)))

    assert compute_match(variant, job) == compute_match(base, job)


@given(profiles, jobs)
def test_p4_missing_required_skills_get_no_credit(profile: MatchProfile, job: MatchJob) -> None:
    """P4 — R3.8, R3.9, R4.3: unmatched listed skills are reported missing and earn nothing.

    **Validates: Requirements 3.8, 3.9, 4.3**
    """
    result = compute_match(profile, job)
    skills = normalize_skills(profile.technical_skills)
    required = normalize_skills(job.required_skills)
    preferred = normalize_skills(job.preferred_skills) - required
    cases = (
        (required, FactorKey.REQUIRED_SKILLS, 35, result.missing_required_skills),
        (preferred, FactorKey.PREFERRED_SKILLS, 10, result.missing_preferred_skills),
    )

    for listed, key, weight, missing in cases:
        assert set(missing) == {display_skill(skill) for skill in listed - skills}
        points = _factor_points(result, key)
        if listed:
            assert points == Fraction(weight * len(listed & skills), len(listed))
            if not listed & skills:
                assert points == 0
    assert not set(result.missing_required_skills) & set(result.matched_required_skills)
    assert not set(result.missing_preferred_skills) & set(result.matched_preferred_skills)


@given(profiles, jobs, st.data())
def test_p5_match_is_deterministic_and_order_independent(
    profile: MatchProfile, job: MatchJob, data: st.DataObject
) -> None:
    """P5 — R3.10, R3.11, R4.6: same inputs in any order give an identical result.

    **Validates: Requirements 3.10, 3.11, 4.6**
    """
    first = compute_match(profile, job)
    shuffled = compute_match(data.draw(permuted_profile(profile)), data.draw(permuted_job(job)))

    assert compute_match(profile, job) == first
    assert shuffled == first
