"""Direct tests for the §5.3 matching helpers: role tokens, location segments, level ordinals and
project grouping (R3.3, design.md §5.3 Clarifications, §5.6)."""

from fractions import Fraction
from itertools import permutations

import pytest

from app.services.matching import (
    EducationLevel,
    ExperienceLevel,
    FactorKey,
    MatchJob,
    MatchProfile,
    ProjectInput,
    WorkMode,
    compute_match,
    location_segments,
    role_tokens,
)
from app.services.matching.engine import (
    EDUCATION_ORDINALS,
    EXPERIENCE_GAP_RATIOS,
    EXPERIENCE_ORDINALS,
    _project_groups,
)


def full_width(text: str) -> str:
    """Map printable ASCII to its full-width form (U+FF01-U+FF5E) and space to U+3000."""
    return "".join("\u3000" if c == " " else chr(ord(c) + 0xFEE0) for c in text)


# ---------- role tokens ----------


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Front-end Developer", {"frontend", "engineer"}),
        ("front end dev", {"frontend", "engineer"}),
        ("Back  End Programmer", {"backend", "engineer"}),
        ("Full Stack SWE Intern", {"fullstack", "software", "engineer"}),
        ("Full-Stack SDE", {"fullstack", "software", "engineer"}),
        ("C++/C# Engineer II", {"c++", "c#", "engineer"}),
        ("Senior ML Engineer (Remote)", {"ml", "engineer"}),
        ("Software Engineer, Backend", {"software", "engineer", "backend"}),
        (full_width("Front-end Developer"), {"frontend", "engineer"}),
        ("Front-ender Role", {"front", "ender", "role"}),
        ("Engineer 2 2024", {"engineer"}),
        ("Data Engineer 3d", {"data", "engineer", "3d"}),
    ],
)
def test_role_tokens_title_yields_expected_set(title: str, expected: set[str]) -> None:
    assert role_tokens(title) == expected


@pytest.mark.parametrize(
    "title",
    ["", "   ", "Intern", "Senior Associate II", "Junior (m/f/d)", "2024 - 2025", "The & Of"],
)
def test_role_tokens_stop_and_digit_only_title_is_empty(title: str) -> None:
    assert role_tokens(title) == frozenset()


def test_role_tokens_is_independent_of_case_and_spacing() -> None:
    assert role_tokens("  FRONTEND   developer ") == role_tokens("frontend Developer")


# ---------- location segments ----------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Berlin, Germany", ("berlin", "germany")),
        (" berlin ,  GERMANY ", ("berlin", "germany")),
        ("Remote", ("remote",)),
        ("", ()),
        ("  ,  , ", ()),
        ("München, Deutschland", ("münchen", "deutschland")),
        ("Straße, DE", ("strasse", "de")),
        (full_width("Berlin,Germany"), ("berlin", "germany")),
        ("Berlin, Germany,,", ("berlin", "germany")),
        ("New\tYork,\nUSA", ("new york", "usa")),
    ],
)
def test_location_segments_text_yields_expected_segments(
    text: str, expected: tuple[str, ...]
) -> None:
    assert location_segments(text) == expected


@pytest.mark.parametrize(
    ("candidate", "expected"),
    [
        ("Berlin", Fraction(1)),
        ("berlin, France", Fraction(1)),
        ("Germany", Fraction(1, 2)),
        ("Munich, GERMANY", Fraction(1, 2)),
        ("Deutschland", Fraction(0)),
        ("Germany, Berlin", Fraction(0)),
    ],
)
def test_location_first_then_last_segment_rule(candidate: str, expected: Fraction) -> None:
    job = MatchJob(id=1, title="Engineer", location="Berlin, Germany", work_mode=WorkMode.ONSITE)
    result = compute_match(MatchProfile(location=candidate), job)
    location = next(f for f in result.factors if f.key == FactorKey.LOCATION)
    assert location.ratio == expected


# ---------- experience ordinals and gap ratios ----------

_LEVELS = ("internship", "entry", "junior", "mid", "senior")
# Rows: user level; columns: job level (same order as _LEVELS).
_EXPERIENCE_TABLE = {
    "internship": ("1", "3/5", "1/5", "0", "0"),
    "entry": ("1", "1", "3/5", "1/5", "0"),
    "junior": ("1", "1", "1", "3/5", "1/5"),
    "mid": ("1", "1", "1", "1", "3/5"),
    "senior": ("1", "1", "1", "1", "1"),
}
_EXPERIENCE_CASES = [
    (user, job, Fraction(_EXPERIENCE_TABLE[user][index]))
    for user in _LEVELS
    for index, job in enumerate(_LEVELS)
]


def test_experience_ordinals_follow_design_order() -> None:
    assert [EXPERIENCE_ORDINALS[ExperienceLevel(level)] for level in _LEVELS] == [0, 1, 2, 3, 4]
    assert dict(EXPERIENCE_GAP_RATIOS) == {1: Fraction(3, 5), 2: Fraction(1, 5)}


@pytest.mark.parametrize(("user", "job", "expected"), _EXPERIENCE_CASES)
def test_experience_ratio_matches_gap_table(user: str, job: str, expected: Fraction) -> None:
    profile = MatchProfile(experience_level=ExperienceLevel(user))
    match_job = MatchJob(
        id=1,
        title="Engineer",
        location="Berlin",
        work_mode=WorkMode.ONSITE,
        experience_level=ExperienceLevel(job),
    )
    result = compute_match(profile, match_job)
    experience = next(f for f in result.factors if f.key == FactorKey.EXPERIENCE)
    assert experience.ratio == expected


# ---------- education ordinals ----------

_EDUCATION = ("high_school", "diploma", "bachelor", "master", "phd")
# Rows: user level; columns: job minimum (same order as _EDUCATION).
_EDUCATION_TABLE = {
    "high_school": ("1", "1/2", "0", "0", "0"),
    "diploma": ("1", "1", "1/2", "0", "0"),
    "bachelor": ("1", "1", "1", "1/2", "0"),
    "master": ("1", "1", "1", "1", "1/2"),
    "phd": ("1", "1", "1", "1", "1"),
}
_EDUCATION_CASES = [
    (user, job, Fraction(_EDUCATION_TABLE[user][index]))
    for user in _EDUCATION
    for index, job in enumerate(_EDUCATION)
]


def test_education_ordinals_follow_design_order() -> None:
    assert [EDUCATION_ORDINALS[EducationLevel(level)] for level in _EDUCATION] == [0, 1, 2, 3, 4]


@pytest.mark.parametrize(("user", "job", "expected"), _EDUCATION_CASES)
def test_education_ratio_matches_level_table(user: str, job: str, expected: Fraction) -> None:
    profile = MatchProfile(education_level=EducationLevel(user))
    match_job = MatchJob(
        id=1,
        title="Engineer",
        location="Berlin",
        work_mode=WorkMode.ONSITE,
        min_education_level=EducationLevel(job),
    )
    result = compute_match(profile, match_job)
    education = next(f for f in result.factors if f.key == FactorKey.EDUCATION)
    assert education.ratio == expected


# ---------- project groups ----------

JOB_SKILLS = frozenset({"react", "typescript", "docker"})


def project(name: str, *technologies: str) -> ProjectInput:
    return ProjectInput(name=name, technologies=technologies)


def test_project_groups_merge_case_variants_and_union_skills() -> None:
    groups = _project_groups(
        (project("Shop", "React"), project(" shop ", "TypeScript"), project("SHOP", "Go")),
        JOB_SKILLS,
    )
    assert len(groups) == 1
    assert groups[0].key == "shop"
    assert groups[0].shared_skills == {"react", "typescript"}


def test_project_groups_skip_blank_names() -> None:
    groups = _project_groups((project("   ", "React"), project("", "Docker")), JOB_SKILLS)
    assert groups == ()


def test_project_groups_alias_technologies_count_toward_job_skills() -> None:
    groups = _project_groups((project("Portfolio", "ReactJS", "ts", "Rust"),), JOB_SKILLS)
    assert groups[0].shared_skills == {"react", "typescript"}


def test_project_groups_irrelevant_group_has_no_shared_skills() -> None:
    groups = _project_groups((project("CLI", "Rust"),), JOB_SKILLS)
    assert groups[0].shared_skills == frozenset()


def test_project_groups_display_name_is_smallest_stripped_name_in_any_order() -> None:
    members = (project("beta", "React"), project(" Beta ", "Docker"), project("BETA", "Go"))
    results = {_project_groups(order, JOB_SKILLS) for order in permutations(members)}
    assert len(results) == 1
    (groups,) = results
    assert groups[0].display_name == "BETA"


def test_project_groups_ordered_by_key() -> None:
    groups = _project_groups(
        (project("zeta", "React"), project("Alpha", "Docker"), project("mid", "Go")), JOB_SKILLS
    )
    assert [group.key for group in groups] == ["alpha", "mid", "zeta"]


def test_project_groups_key_does_not_collapse_inner_whitespace() -> None:
    groups = _project_groups((project("My App", "React"), project("My  App", "React")), JOB_SKILLS)
    assert [group.key for group in groups] == ["my  app", "my app"]
