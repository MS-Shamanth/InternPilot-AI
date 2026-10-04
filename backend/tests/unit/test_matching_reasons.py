"""Reason templates, polarity, ordering and `detail` strings of `compute_match`
(R4.1-R4.6; design.md §5.4, §5.5).

Every expected string below is copied from the design tables, not from the engine.
"""

from dataclasses import dataclass, replace

import pytest

from app.services.matching import (
    FACTOR_SPECS,
    EducationLevel,
    ExperienceLevel,
    FactorKey,
    MatchJob,
    MatchProfile,
    MatchResult,
    ProjectInput,
    WorkMode,
    compute_match,
    round_half_up,
)

POSITIVE = "+"
NEGATIVE = "-"

BASE_PROFILE = MatchProfile()
BASE_JOB = MatchJob(
    id=1, title="Software Engineer", location="Berlin, Germany", work_mode=WorkMode.ONSITE
)
PYTHON_JOB = replace(BASE_JOB, required_skills=("Python",))


@dataclass(frozen=True)
class ReasonCase:
    factor: FactorKey
    polarity: str
    reason: str
    detail: str
    profile: MatchProfile = BASE_PROFILE
    job: MatchJob = BASE_JOB


def _profile(**changes: object) -> MatchProfile:
    return replace(BASE_PROFILE, **changes)


def _job(**changes: object) -> MatchJob:
    return replace(BASE_JOB, **changes)


CASES: dict[str, ReasonCase] = {
    # ---- required skills ----
    "required_matched": ReasonCase(
        FactorKey.REQUIRED_SKILLS,
        POSITIVE,
        "Python matches required skill",
        "1 of 1 required skills matched",
        profile=_profile(technical_skills=("python",)),
        job=PYTHON_JOB,
    ),
    "required_missing": ReasonCase(
        FactorKey.REQUIRED_SKILLS,
        NEGATIVE,
        "Java experience is missing (required)",
        "0 of 1 required skills matched",
        job=_job(required_skills=("Java",)),
    ),
    "required_none_listed": ReasonCase(
        FactorKey.REQUIRED_SKILLS,
        POSITIVE,
        "No required skills listed for this role",
        "none listed",
    ),
    # ---- preferred skills ----
    "preferred_matched": ReasonCase(
        FactorKey.PREFERRED_SKILLS,
        POSITIVE,
        "Docker matches preferred skill",
        "1 of 1 preferred skills matched",
        profile=_profile(technical_skills=("Docker",)),
        job=_job(preferred_skills=("docker",)),
    ),
    "preferred_missing": ReasonCase(
        FactorKey.PREFERRED_SKILLS,
        NEGATIVE,
        "Docker is a preferred skill not in your profile",
        "0 of 1 preferred skills matched",
        job=_job(preferred_skills=("Docker",)),
    ),
    # ---- role similarity (title tokens {software, engineer}) ----
    "role_full": ReasonCase(
        FactorKey.ROLE_SIMILARITY,
        POSITIVE,
        'Job title matches your target role "Software Engineer Intern"',
        "best match: Software Engineer Intern",
        profile=_profile(target_roles=("Software Engineer Intern",)),
    ),
    "role_partial_half_is_positive": ReasonCase(
        FactorKey.ROLE_SIMILARITY,
        POSITIVE,
        'Job title partially matches your target role "Data Engineer"',
        "best match: Data Engineer",
        profile=_profile(target_roles=("Data Engineer",)),
    ),
    "role_partial_below_half_is_negative": ReasonCase(
        FactorKey.ROLE_SIMILARITY,
        NEGATIVE,
        'Job title partially matches your target role "Machine Learning Engineer"',
        "best match: Machine Learning Engineer",
        profile=_profile(target_roles=("Machine Learning Engineer",)),
    ),
    "role_none": ReasonCase(
        FactorKey.ROLE_SIMILARITY,
        NEGATIVE,
        "Job title does not match your target roles",
        "best match: Data Analyst",
        profile=_profile(target_roles=("Data Analyst",)),
    ),
    "role_no_usable_roles": ReasonCase(
        FactorKey.ROLE_SIMILARITY,
        NEGATIVE,
        "Add target roles to your profile to improve role matching",
        "no target roles",
        profile=_profile(target_roles=("Intern",)),
    ),
    "role_no_title_terms": ReasonCase(
        FactorKey.ROLE_SIMILARITY,
        NEGATIVE,
        "Job title has no comparable role terms",
        "no comparable title terms",
        profile=_profile(target_roles=("Data Analyst",)),
        job=_job(title="Senior Intern"),
    ),
    # ---- experience ----
    "experience_meets": ReasonCase(
        FactorKey.EXPERIENCE,
        POSITIVE,
        "Your entry experience meets the internship level",
        "entry profile, internship role",
        profile=_profile(experience_level=ExperienceLevel.ENTRY),
        job=_job(experience_level=ExperienceLevel.INTERNSHIP),
    ),
    "experience_gap_one": ReasonCase(
        FactorKey.EXPERIENCE,
        NEGATIVE,
        "Role expects entry level; your profile is internship",
        "internship profile, entry role",
        profile=_profile(experience_level=ExperienceLevel.INTERNSHIP),
        job=_job(experience_level=ExperienceLevel.ENTRY),
    ),
    "experience_gap_two": ReasonCase(
        FactorKey.EXPERIENCE,
        NEGATIVE,
        "Role expects junior level; your profile is internship",
        "internship profile, junior role",
        profile=_profile(experience_level=ExperienceLevel.INTERNSHIP),
        job=_job(experience_level=ExperienceLevel.JUNIOR),
    ),
    "experience_well_above": ReasonCase(
        FactorKey.EXPERIENCE,
        NEGATIVE,
        "Role expects mid level, well above your internship level",
        "internship profile, mid role",
        profile=_profile(experience_level=ExperienceLevel.INTERNSHIP),
        job=_job(experience_level=ExperienceLevel.MID),
    ),
    "experience_profile_missing": ReasonCase(
        FactorKey.EXPERIENCE,
        NEGATIVE,
        "Experience level not specified",
        "level not specified",
        job=_job(experience_level=ExperienceLevel.MID),
    ),
    "experience_job_missing": ReasonCase(
        FactorKey.EXPERIENCE,
        NEGATIVE,
        "Experience level not specified",
        "level not specified",
        profile=_profile(experience_level=ExperienceLevel.MID),
    ),
    # ---- location ----
    "location_remote": ReasonCase(
        FactorKey.LOCATION,
        POSITIVE,
        "Remote role, location-independent",
        "remote role",
        job=_job(work_mode=WorkMode.REMOTE),
    ),
    "location_city_matches": ReasonCase(
        FactorKey.LOCATION,
        POSITIVE,
        "Berlin, Germany matches your location or preferred locations",
        "city or region matches",
        profile=_profile(location="Berlin"),
    ),
    "location_country_matches": ReasonCase(
        FactorKey.LOCATION,
        POSITIVE,
        "Berlin, Germany is in a country you prefer",
        "country matches",
        profile=_profile(preferred_locations=("Munich, Germany",)),
    ),
    "location_outside": ReasonCase(
        FactorKey.LOCATION,
        NEGATIVE,
        "Berlin, Germany is outside your preferred locations",
        "outside preferred locations",
        profile=_profile(location="Paris, France"),
    ),
    "location_none_in_profile": ReasonCase(
        FactorKey.LOCATION,
        NEGATIVE,
        "Add a location or preferred locations to your profile",
        "no locations in profile",
    ),
    # ---- work mode ----
    "work_mode_onsite_preferred": ReasonCase(
        FactorKey.WORK_MODE,
        POSITIVE,
        "Onsite work matches your preference",
        "Onsite is preferred",
        profile=_profile(preferred_work_modes=(WorkMode.ONSITE,)),
    ),
    "work_mode_remote_preferred": ReasonCase(
        FactorKey.WORK_MODE,
        POSITIVE,
        "Remote work matches your preference",
        "Remote is preferred",
        profile=_profile(preferred_work_modes=(WorkMode.REMOTE,)),
        job=_job(work_mode=WorkMode.REMOTE),
    ),
    "work_mode_hybrid_partial": ReasonCase(
        FactorKey.WORK_MODE,
        POSITIVE,
        "Hybrid work partially matches your preference",
        "Hybrid is a partial match",
        profile=_profile(preferred_work_modes=(WorkMode.REMOTE,)),
        job=_job(work_mode=WorkMode.HYBRID),
    ),
    "work_mode_onsite_not_preferred": ReasonCase(
        FactorKey.WORK_MODE,
        NEGATIVE,
        "Onsite work does not match your preferred work modes",
        "Onsite is not preferred",
        profile=_profile(preferred_work_modes=(WorkMode.REMOTE, WorkMode.HYBRID)),
    ),
    "work_mode_remote_not_preferred": ReasonCase(
        FactorKey.WORK_MODE,
        NEGATIVE,
        "Remote work does not match your preferred work modes",
        "Remote is not preferred",
        profile=_profile(preferred_work_modes=(WorkMode.ONSITE,)),
        job=_job(work_mode=WorkMode.REMOTE),
    ),
    "work_mode_none_preferred": ReasonCase(
        FactorKey.WORK_MODE,
        NEGATIVE,
        "Add preferred work modes to your profile",
        "no preferred work modes",
    ),
    # ---- education ----
    "education_no_requirement": ReasonCase(
        FactorKey.EDUCATION,
        POSITIVE,
        "No minimum education requirement",
        "no minimum requirement",
    ),
    "education_meets_bachelor": ReasonCase(
        FactorKey.EDUCATION,
        POSITIVE,
        "Your education meets the bachelor's requirement",
        "meets bachelor's",
        profile=_profile(education_level=EducationLevel.MASTER),
        job=_job(min_education_level=EducationLevel.BACHELOR),
    ),
    "education_meets_high_school": ReasonCase(
        FactorKey.EDUCATION,
        POSITIVE,
        "Your education meets the high school requirement",
        "meets high school",
        profile=_profile(education_level=EducationLevel.HIGH_SCHOOL),
        job=_job(min_education_level=EducationLevel.HIGH_SCHOOL),
    ),
    "education_one_below_master": ReasonCase(
        FactorKey.EDUCATION,
        NEGATIVE,
        "Role prefers master's; you are one level below",
        "one level below master's",
        profile=_profile(education_level=EducationLevel.BACHELOR),
        job=_job(min_education_level=EducationLevel.MASTER),
    ),
    "education_one_below_diploma": ReasonCase(
        FactorKey.EDUCATION,
        NEGATIVE,
        "Role prefers diploma; you are one level below",
        "one level below diploma",
        profile=_profile(education_level=EducationLevel.HIGH_SCHOOL),
        job=_job(min_education_level=EducationLevel.DIPLOMA),
    ),
    "education_below_phd": ReasonCase(
        FactorKey.EDUCATION,
        NEGATIVE,
        "Role requires PhD education",
        "below PhD",
        profile=_profile(education_level=EducationLevel.BACHELOR),
        job=_job(min_education_level=EducationLevel.PHD),
    ),
    "education_not_specified": ReasonCase(
        FactorKey.EDUCATION,
        NEGATIVE,
        "Education level not specified in your profile",
        "education not specified",
        job=_job(min_education_level=EducationLevel.DIPLOMA),
    ),
    # ---- project relevance (J = {python, sql}) ----
    "projects_one_relevant": ReasonCase(
        FactorKey.PROJECTS,
        POSITIVE,
        'Project "Portfolio" uses Python',
        "1 of 2 projects use the role's skills",
        profile=_profile(
            projects=(
                ProjectInput("Portfolio", ("SQL", "Python")),
                ProjectInput("Notes", ("Rust",)),
            )
        ),
        job=_job(required_skills=("Python", "SQL")),
    ),
    "projects_two_relevant": ReasonCase(
        FactorKey.PROJECTS,
        POSITIVE,
        'Project "Alpha" uses SQL (+1 more relevant projects)',
        "2 of 2 projects use the role's skills",
        profile=_profile(
            projects=(ProjectInput("Beta", ("Python",)), ProjectInput("Alpha", ("SQL",)))
        ),
        job=_job(required_skills=("Python", "SQL")),
    ),
    "projects_three_relevant": ReasonCase(
        FactorKey.PROJECTS,
        POSITIVE,
        'Project "Alpha" uses Python (+2 more relevant projects)',
        "3 of 3 projects use the role's skills",
        profile=_profile(
            projects=(
                ProjectInput("Gamma", ("Python",)),
                ProjectInput("Beta", ("Python",)),
                ProjectInput("Alpha", ("Python",)),
            )
        ),
        job=PYTHON_JOB,
    ),
    "projects_none_relevant": ReasonCase(
        FactorKey.PROJECTS,
        NEGATIVE,
        "No projects demonstrate this role's skills",
        "0 of 1 projects use the role's skills",
        profile=_profile(projects=(ProjectInput("Notes", ("Rust",)),)),
        job=PYTHON_JOB,
    ),
    "projects_no_projects": ReasonCase(
        FactorKey.PROJECTS,
        NEGATIVE,
        "No projects demonstrate this role's skills",
        "0 of 0 projects use the role's skills",
        job=PYTHON_JOB,
    ),
    "projects_no_job_skills": ReasonCase(
        FactorKey.PROJECTS,
        NEGATIVE,
        "Role lists no skills to compare projects against",
        "no job skills to compare",
        profile=_profile(projects=(ProjectInput("Notes", ("Rust",)),)),
    ),
}

CASE_PARAMS = [pytest.param(case, id=name) for name, case in CASES.items()]


def _factor_detail(result: MatchResult, key: FactorKey) -> str:
    return next(factor.detail for factor in result.factors if factor.key == key)


# ---------- templates and detail strings (R4.3-R4.5, §5.4, §5.5) ----------


@pytest.mark.parametrize("case", CASE_PARAMS)
def test_reason_template_has_design_text_and_polarity(case: ReasonCase) -> None:
    result = compute_match(case.profile, case.job)
    expected, other = (
        (result.positive_reasons, result.negative_reasons)
        if case.polarity == POSITIVE
        else (result.negative_reasons, result.positive_reasons)
    )
    assert case.reason in expected
    assert case.reason not in other


@pytest.mark.parametrize("case", CASE_PARAMS)
def test_factor_detail_has_design_text(case: ReasonCase) -> None:
    result = compute_match(case.profile, case.job)
    assert _factor_detail(result, case.factor) == case.detail


def test_preferred_none_listed_has_detail_and_no_reason() -> None:
    result = compute_match(BASE_PROFILE, BASE_JOB)
    assert _factor_detail(result, FactorKey.PREFERRED_SKILLS) == "none listed"
    reasons = (*result.positive_reasons, *result.negative_reasons)
    assert not any("preferred skill" in reason for reason in reasons)


def test_preferred_skill_also_required_counts_only_as_required() -> None:
    job = _job(required_skills=("Python",), preferred_skills=("python",))
    result = compute_match(_profile(technical_skills=("Python",)), job)
    assert "Python matches required skill" in result.positive_reasons
    assert "Python matches preferred skill" not in result.positive_reasons
    assert _factor_detail(result, FactorKey.PREFERRED_SKILLS) == "none listed"


@pytest.mark.parametrize("case", CASE_PARAMS)
def test_non_skill_factors_emit_exactly_one_reason_each(case: ReasonCase) -> None:
    """R4.5: role, experience, location, work mode, education and projects add one reason each;
    skills add one per matched/missing skill (one "none listed" reason for required only)."""
    result = compute_match(case.profile, case.job)
    required = len(result.matched_required_skills) + len(result.missing_required_skills)
    preferred = len(result.matched_preferred_skills) + len(result.missing_preferred_skills)
    skill_reasons = (required or 1) + preferred
    assert len(result.positive_reasons) + len(result.negative_reasons) == skill_reasons + 6


@pytest.mark.parametrize("case", CASE_PARAMS)
def test_every_factor_has_detail_and_exact_points(case: ReasonCase) -> None:
    """R4.1, R4.2: eight ordered factors, each with a detail; points and score are exact."""
    result = compute_match(case.profile, case.job)
    assert [factor.key for factor in result.factors] == [spec.key for spec in FACTOR_SPECS]
    assert all(factor.detail for factor in result.factors)
    assert all(factor.points == factor.weight * factor.ratio for factor in result.factors)
    assert result.score == round_half_up(result.total_points)


# ---------- ordering (R4.6) ----------

ORDERING_PROFILE = MatchProfile(
    technical_skills=("C++", "aws", "C#", "Angular", "Spark"),
    target_roles=("Software Engineer",),
    location="Paris, France",
    preferred_work_modes=(WorkMode.ONSITE,),
    experience_level=ExperienceLevel.JUNIOR,
    education_level=EducationLevel.BACHELOR,
    projects=(ProjectInput("Site", ("Angular",)),),
)
# Normalized order differs from display order: "angular" < "aws" but "AWS" < "Angular";
# "spark" < "sql" but "SQL" < "Spark".
ORDERING_JOB = MatchJob(
    id=7,
    title="Software Engineer",
    location="Berlin, Germany",
    work_mode=WorkMode.ONSITE,
    experience_level=ExperienceLevel.SENIOR,
    min_education_level=EducationLevel.MASTER,
    required_skills=("C++", "AWS", ".NET", "Angular", "C#", "Go"),
    preferred_skills=("SQL", "Spark", "TypeScript", "Kubernetes"),
)


def test_reasons_follow_factor_order_then_normalized_skill_name() -> None:
    result = compute_match(ORDERING_PROFILE, ORDERING_JOB)
    assert result.positive_reasons == (
        "Angular matches required skill",
        "AWS matches required skill",
        "C# matches required skill",
        "C++ matches required skill",
        "Spark matches preferred skill",
        'Job title matches your target role "Software Engineer"',
        "Onsite work matches your preference",
        'Project "Site" uses Angular',
    )
    assert result.negative_reasons == (
        ".NET experience is missing (required)",
        "Go experience is missing (required)",
        "Kubernetes is a preferred skill not in your profile",
        "SQL is a preferred skill not in your profile",
        "TypeScript is a preferred skill not in your profile",
        "Role expects senior level; your profile is junior",
        "Berlin, Germany is outside your preferred locations",
        "Role prefers master's; you are one level below",
    )


def test_skill_lists_sorted_by_normalized_name() -> None:
    result = compute_match(ORDERING_PROFILE, ORDERING_JOB)
    assert result.matched_required_skills == ("Angular", "AWS", "C#", "C++")
    assert result.missing_required_skills == (".NET", "Go")
    assert result.matched_preferred_skills == ("Spark",)
    assert result.missing_preferred_skills == ("Kubernetes", "SQL", "TypeScript")


def test_reason_order_is_independent_of_input_order() -> None:
    shuffled_profile = replace(
        ORDERING_PROFILE, technical_skills=tuple(reversed(ORDERING_PROFILE.technical_skills))
    )
    shuffled_job = replace(
        ORDERING_JOB,
        required_skills=tuple(reversed(ORDERING_JOB.required_skills)),
        preferred_skills=tuple(reversed(ORDERING_JOB.preferred_skills)),
    )
    shuffled = compute_match(shuffled_profile, shuffled_job)
    original = compute_match(ORDERING_PROFILE, ORDERING_JOB)
    assert shuffled.positive_reasons == original.positive_reasons
    assert shuffled.negative_reasons == original.negative_reasons


def test_best_role_tie_uses_casefold_then_original_order() -> None:
    profile = _profile(target_roles=("software engineer", "Software Engineer", "Data Engineer"))
    result = compute_match(profile, BASE_JOB)
    assert result.positive_reasons[1] == 'Job title matches your target role "Software Engineer"'
    assert _factor_detail(result, FactorKey.ROLE_SIMILARITY) == "best match: Software Engineer"


def test_project_group_display_name_is_smallest_original_name() -> None:
    projects = (ProjectInput("portfolio", ("Python",)), ProjectInput(" Portfolio ", ()))
    profile = _profile(projects=projects)
    result = compute_match(profile, PYTHON_JOB)
    assert 'Project "Portfolio" uses Python' in result.positive_reasons
    assert _factor_detail(result, FactorKey.PROJECTS) == "1 of 1 projects use the role's skills"
