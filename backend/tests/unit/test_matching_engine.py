"""Unit tests for `compute_match` scoring, rounding and determinism (R3.1, R3.3, R3.4, R3.7,
R3.8, R3.10, R3.11, R4.1, R4.2, R4.6; design.md §5.3-§5.6)."""

from dataclasses import replace
from fractions import Fraction

import pytest

from app.schemas import common as schema_enums
from app.services.matching import (
    ALGORITHM_VERSION,
    FACTOR_SPECS,
    FACTOR_WEIGHTS,
    EducationLevel,
    ExperienceLevel,
    FactorKey,
    MatchJob,
    MatchProfile,
    ProjectInput,
    WorkMode,
    clamp_score,
    compute_match,
    round_half_up,
    to_rounded_float,
)

WORKED_PROFILE = MatchProfile(
    technical_skills=("ReactJS", "python", "SQL", "Docker", "ML"),
    target_roles=("Frontend Developer Intern",),
    location="Berlin, Germany",
    preferred_locations=(),
    preferred_work_modes=(WorkMode.REMOTE,),
    experience_level=ExperienceLevel.ENTRY,
    education_level=EducationLevel.BACHELOR,
    projects=(ProjectInput(name="Portfolio", technologies=("React",)),),
)
WORKED_JOB = MatchJob(
    id=12,
    title="Front-End Engineer",
    location="Munich, Germany",
    work_mode=WorkMode.ONSITE,
    experience_level=ExperienceLevel.INTERNSHIP,
    min_education_level=EducationLevel.BACHELOR,
    required_skills=("Python", "React", "SQL", "Java"),
    preferred_skills=("Docker", "Machine Learning"),
)
EMPTY_JOB = MatchJob(id=1, title="Engineer", location="Berlin", work_mode=WorkMode.ONSITE)

MAX_PROFILE = MatchProfile(
    technical_skills=("Python",),
    target_roles=("Software Engineer",),
    location="Berlin",
    preferred_work_modes=(WorkMode.ONSITE,),
    experience_level=ExperienceLevel.SENIOR,
    education_level=EducationLevel.PHD,
    projects=(ProjectInput("A", ("Python",)), ProjectInput("B", ("Python",))),
)
MAX_JOB = replace(
    EMPTY_JOB,
    title="Software Engineer",
    experience_level=ExperienceLevel.INTERNSHIP,
    required_skills=("Python",),
)
MIN_PROFILE = MatchProfile(
    technical_skills=("Rust",),
    target_roles=("Data Analyst",),
    location="Paris, France",
    preferred_work_modes=(WorkMode.REMOTE,),
    experience_level=ExperienceLevel.INTERNSHIP,
    education_level=EducationLevel.HIGH_SCHOOL,
)
MIN_JOB = MatchJob(
    id=2,
    title="Software Engineer",
    location="Berlin, Germany",
    work_mode=WorkMode.ONSITE,
    experience_level=ExperienceLevel.SENIOR,
    min_education_level=EducationLevel.MASTER,
    required_skills=("Python",),
    preferred_skills=("Docker",),
)


# ---------- constants ----------


def test_factor_weights_sum_to_100() -> None:
    assert sum(FACTOR_WEIGHTS.values()) == 100


def test_factor_specs_follow_design_order_labels_and_weights() -> None:
    assert [(s.key.value, s.label, s.weight) for s in FACTOR_SPECS] == [
        ("required_skills", "Required skills", 35),
        ("preferred_skills", "Preferred skills", 10),
        ("role_similarity", "Role similarity", 15),
        ("experience", "Experience", 15),
        ("location", "Location", 10),
        ("work_mode", "Work mode", 5),
        ("education", "Education", 5),
        ("projects", "Project relevance", 5),
    ]


@pytest.mark.parametrize(
    ("engine_enum", "schema_enum"),
    [
        (WorkMode, schema_enums.WorkMode),
        (ExperienceLevel, schema_enums.ExperienceLevel),
        (EducationLevel, schema_enums.EducationLevel),
    ],
)
def test_engine_enums_mirror_schema_enum_values(engine_enum: type, schema_enum: type) -> None:
    assert [m.value for m in engine_enum] == [m.value for m in schema_enum]


def test_compute_match_accepts_schema_enum_values() -> None:
    schema_profile = replace(
        WORKED_PROFILE,
        preferred_work_modes=(schema_enums.WorkMode.REMOTE,),
        experience_level=schema_enums.ExperienceLevel.ENTRY,
        education_level=schema_enums.EducationLevel.BACHELOR,
    )
    assert compute_match(schema_profile, WORKED_JOB) == compute_match(WORKED_PROFILE, WORKED_JOB)


# ---------- worked example ----------


def test_compute_match_worked_example_exact() -> None:
    result = compute_match(WORKED_PROFILE, WORKED_JOB)
    points = {f.key: f.points for f in result.factors}
    assert points == {
        FactorKey.REQUIRED_SKILLS: Fraction(105, 4),  # 3 of 4 -> 26.25
        FactorKey.PREFERRED_SKILLS: 10,  # 2 of 2
        FactorKey.ROLE_SIMILARITY: 15,  # {frontend, engineer} both match
        FactorKey.EXPERIENCE: 15,  # entry >= internship
        FactorKey.LOCATION: 5,  # same country only
        FactorKey.WORK_MODE: 0,  # onsite, prefers remote
        FactorKey.EDUCATION: 5,  # bachelor meets bachelor
        FactorKey.PROJECTS: 3,  # one relevant project
    }
    assert result.total_points == Fraction(317, 4)  # 79.25
    assert result.score == 79
    assert result.job_id == 12
    assert result.algorithm_version == ALGORITHM_VERSION == "1.0.0"
    assert result.matched_required_skills == ("Python", "React", "SQL")
    assert result.missing_required_skills == ("Java",)
    assert result.matched_preferred_skills == ("Docker", "Machine Learning")
    assert result.missing_preferred_skills == ()


def test_compute_match_worked_example_reasons_in_factor_order() -> None:
    result = compute_match(WORKED_PROFILE, WORKED_JOB)
    assert result.positive_reasons == (
        "Python matches required skill",
        "React matches required skill",
        "SQL matches required skill",
        "Docker matches preferred skill",
        "Machine Learning matches preferred skill",
        'Job title matches your target role "Frontend Developer Intern"',
        "Your entry experience meets the internship level",
        "Munich, Germany is in a country you prefer",
        "Your education meets the bachelor's requirement",
        'Project "Portfolio" uses React',
    )
    assert result.negative_reasons == (
        "Java experience is missing (required)",
        "Onsite work does not match your preferred work modes",
    )


def test_compute_match_returns_eight_factors_with_exact_points() -> None:
    result = compute_match(WORKED_PROFILE, WORKED_JOB)
    assert [f.key for f in result.factors] == [s.key for s in FACTOR_SPECS]
    assert all(f.points == f.weight * f.ratio for f in result.factors)
    assert all(0 <= f.ratio <= 1 for f in result.factors)


# ---------- rounding and bounds ----------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Fraction(1, 2), 1),
        (Fraction(5, 2), 3),
        (Fraction(115, 2), 58),
        (Fraction(249, 100), 2),
        (Fraction(-1, 2), 0),
        (Fraction(317, 4), 79),
    ],
)
def test_round_half_up_boundaries_round_ties_up(value: Fraction, expected: int) -> None:
    assert round_half_up(value) == expected


@pytest.mark.parametrize(("value", "expected"), [(-1, 0), (0, 0), (57, 57), (100, 100), (101, 100)])
def test_clamp_score_limits_to_0_100(value: int, expected: int) -> None:
    assert clamp_score(value) == expected


@pytest.mark.parametrize(
    ("value", "places", "expected"),
    [
        (Fraction(35, 3), 2, 11.67),
        (Fraction(1, 3), 4, 0.3333),
        (Fraction(2, 3), 4, 0.6667),
        (Fraction(1, 8), 2, 0.13),
        (Fraction(10), 2, 10.0),
    ],
)
def test_to_rounded_float_rounds_half_up(value: Fraction, places: int, expected: float) -> None:
    assert to_rounded_float(value, places) == expected


def test_compute_match_half_point_total_rounds_up() -> None:
    profile = MatchProfile(technical_skills=("Python",), preferred_work_modes=(WorkMode.ONSITE,))
    job = replace(EMPTY_JOB, required_skills=("Python", "Java"))
    # 17.5 + 10 + 7.5 + 7.5 + 5 + 5 + 5 + 0
    result = compute_match(profile, job)
    assert result.total_points == Fraction(115, 2)
    assert result.score == 58


def test_compute_match_all_factors_maxed_scores_100() -> None:
    result = compute_match(MAX_PROFILE, MAX_JOB)
    assert result.score == 100
    assert result.negative_reasons == ()


def test_compute_match_all_factors_zero_scores_0() -> None:
    result = compute_match(MIN_PROFILE, MIN_JOB)
    assert result.score == 0
    assert result.positive_reasons == ()


def test_compute_match_empty_profile_and_job_stays_in_range() -> None:
    result = compute_match(MatchProfile(), EMPTY_JOB)
    # 35 + 10 + 7.5 + 7.5 + 5 + 2.5 + 5 + 2.5
    assert result.total_points == 75
    assert result.score == 75


# ---------- credit, duplicates, determinism ----------


def test_compute_match_missing_required_skills_get_no_credit() -> None:
    profile = replace(WORKED_PROFILE, technical_skills=("Python", "Docker"))
    result = compute_match(profile, WORKED_JOB)
    required = result.factors[0]
    assert required.points == Fraction(35, 4)
    assert "React" in result.missing_required_skills
    assert "React" not in result.matched_required_skills


def test_compute_match_duplicate_skill_variants_equal_deduplicated() -> None:
    duplicated = replace(
        WORKED_PROFILE,
        technical_skills=(
            *("ReactJS", "react", " React ", "React.", "python", "Python3"),
            *("SQL", "sql", "Docker", "ML", "machine learning"),
        ),
    )
    assert compute_match(duplicated, WORKED_JOB) == compute_match(WORKED_PROFILE, WORKED_JOB)


def test_compute_match_same_inputs_twice_are_equal() -> None:
    assert compute_match(WORKED_PROFILE, WORKED_JOB) == compute_match(WORKED_PROFILE, WORKED_JOB)


def test_compute_match_permuted_inputs_are_equal() -> None:
    profile = replace(
        WORKED_PROFILE,
        target_roles=("Data Engineer", "backend engineer", "Frontend Developer Intern"),
        preferred_locations=("Paris", "Munich, Germany"),
        preferred_work_modes=(WorkMode.REMOTE, WorkMode.HYBRID),
        projects=(
            ProjectInput("Zeta", ("Docker",)),
            ProjectInput("alpha", ("SQL", "React")),
            ProjectInput("Alpha", ("Python",)),
        ),
    )
    permuted = replace(
        profile,
        technical_skills=tuple(reversed(profile.technical_skills)),
        target_roles=tuple(reversed(profile.target_roles)),
        preferred_locations=tuple(reversed(profile.preferred_locations)),
        preferred_work_modes=tuple(reversed(profile.preferred_work_modes)),
        projects=tuple(reversed(profile.projects)),
    )
    job = replace(
        WORKED_JOB,
        required_skills=tuple(reversed(WORKED_JOB.required_skills)),
        preferred_skills=tuple(reversed(WORKED_JOB.preferred_skills)),
    )
    assert compute_match(permuted, job) == compute_match(profile, WORKED_JOB)


def test_compute_match_adding_unrelated_skill_changes_nothing() -> None:
    extended = replace(
        WORKED_PROFILE, technical_skills=(*WORKED_PROFILE.technical_skills, "Haskell")
    )
    assert compute_match(extended, WORKED_JOB) == compute_match(WORKED_PROFILE, WORKED_JOB)
