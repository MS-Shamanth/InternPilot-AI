"""Unit tests for each §5.3 factor case and its §5.4 reason template (R3.3, R3.8, R3.9, R4.3-R4.5).

Every test isolates one factor: the other factors' reasons are filtered out by looking only at
the factor's own `FactorResult` and the reason text it is documented to emit.
"""

from dataclasses import replace
from fractions import Fraction

from app.services.matching import (
    EducationLevel,
    ExperienceLevel,
    FactorKey,
    FactorResult,
    MatchJob,
    MatchProfile,
    MatchResult,
    ProjectInput,
    WorkMode,
    compute_match,
    location_segments,
    role_tokens,
)
from app.services.matching.engine import ROLE_STOP_TOKENS

BASE_JOB = MatchJob(
    id=1, title="Software Engineer", location="Berlin, Germany", work_mode=WorkMode.ONSITE
)
EMPTY_PROFILE = MatchProfile()


def match(profile: MatchProfile = EMPTY_PROFILE, **job_overrides: object) -> MatchResult:
    return compute_match(profile, replace(BASE_JOB, **job_overrides))


def factor(result: MatchResult, key: FactorKey) -> FactorResult:
    return next(f for f in result.factors if f.key == key)


def reasons(result: MatchResult) -> tuple[str, ...]:
    return result.positive_reasons + result.negative_reasons


# ---------- 1. required skills ----------


def test_required_no_skills_listed_full_credit_with_reason() -> None:
    result = match()
    required = factor(result, FactorKey.REQUIRED_SKILLS)
    assert (required.ratio, required.points, required.detail) == (1, 35, "none listed")
    assert "No required skills listed for this role" in result.positive_reasons


def test_required_partial_match_points_are_weight_times_fraction() -> None:
    profile = MatchProfile(technical_skills=("Python",))
    result = match(profile, required_skills=("Python", "Java", "Go"))
    required = factor(result, FactorKey.REQUIRED_SKILLS)
    assert required.ratio == Fraction(1, 3)
    assert required.points == Fraction(35, 3)
    assert required.detail == "1 of 3 required skills matched"


def test_required_no_overlap_awards_zero_points() -> None:
    profile = MatchProfile(technical_skills=("Rust",))
    result = match(profile, required_skills=("Python", "Java"))
    assert factor(result, FactorKey.REQUIRED_SKILLS).points == 0
    assert result.matched_required_skills == ()
    assert result.missing_required_skills == ("Java", "Python")


def test_required_matched_skill_emits_positive_template() -> None:
    profile = MatchProfile(technical_skills=("python",))
    result = match(profile, required_skills=("Python",))
    assert "Python matches required skill" in result.positive_reasons


def test_required_missing_skill_emits_negative_template() -> None:
    result = match(required_skills=("Java",))
    assert "Java experience is missing (required)" in result.negative_reasons


def test_required_alias_in_profile_matches_canonical_skill() -> None:
    profile = MatchProfile(technical_skills=("ReactJS", "Postgres"))
    result = match(profile, required_skills=("React", "PostgreSQL"))
    assert factor(result, FactorKey.REQUIRED_SKILLS).ratio == 1
    assert result.matched_required_skills == ("PostgreSQL", "React")


def test_required_skill_normalizing_to_none_is_ignored() -> None:
    result = match(required_skills=("  ,; ", "Python"))
    assert factor(result, FactorKey.REQUIRED_SKILLS).detail == "0 of 1 required skills matched"


# ---------- 2. preferred skills ----------


def test_preferred_no_skills_listed_full_credit_without_reason() -> None:
    result = match()
    preferred = factor(result, FactorKey.PREFERRED_SKILLS)
    assert (preferred.ratio, preferred.points, preferred.detail) == (1, 10, "none listed")
    assert not any("preferred skill" in reason for reason in reasons(result))


def test_preferred_skill_also_required_counts_only_as_required() -> None:
    profile = MatchProfile(technical_skills=("Python",))
    result = match(profile, required_skills=("Python",), preferred_skills=("python", "Docker"))
    preferred = factor(result, FactorKey.PREFERRED_SKILLS)
    assert preferred.detail == "0 of 1 preferred skills matched"
    assert result.missing_preferred_skills == ("Docker",)


def test_preferred_partial_match_points_are_weight_times_fraction() -> None:
    profile = MatchProfile(technical_skills=("Docker",))
    result = match(profile, preferred_skills=("Docker", "AWS"))
    preferred = factor(result, FactorKey.PREFERRED_SKILLS)
    assert (preferred.ratio, preferred.points) == (Fraction(1, 2), 5)


def test_preferred_no_overlap_awards_zero_points() -> None:
    result = match(preferred_skills=("Docker",))
    assert factor(result, FactorKey.PREFERRED_SKILLS).points == 0


def test_preferred_matched_and_missing_emit_templates() -> None:
    profile = MatchProfile(technical_skills=("docker",))
    result = match(profile, preferred_skills=("Docker", "AWS"))
    assert "Docker matches preferred skill" in result.positive_reasons
    assert "AWS is a preferred skill not in your profile" in result.negative_reasons


# ---------- 3. role similarity ----------


def test_role_no_target_roles_neutral_with_reason() -> None:
    result = match()
    role = factor(result, FactorKey.ROLE_SIMILARITY)
    assert (role.ratio, role.detail) == (Fraction(1, 2), "no target roles")
    assert "Add target roles to your profile to improve role matching" in result.negative_reasons


def test_role_stop_token_only_roles_are_not_usable() -> None:
    result = match(MatchProfile(target_roles=("Intern", "Senior", "2025")))
    assert factor(result, FactorKey.ROLE_SIMILARITY).detail == "no target roles"


def test_role_title_without_terms_neutral_with_reason() -> None:
    result = match(MatchProfile(target_roles=("Data Analyst",)), title="Junior Intern")
    role = factor(result, FactorKey.ROLE_SIMILARITY)
    assert (role.ratio, role.detail) == (Fraction(1, 2), "no comparable title terms")
    assert "Job title has no comparable role terms" in result.negative_reasons


def test_role_full_match_emits_positive_template() -> None:
    profile = MatchProfile(target_roles=("Frontend Developer Intern",))
    result = match(profile, title="Front-End Engineer")
    role = factor(result, FactorKey.ROLE_SIMILARITY)
    assert (role.ratio, role.detail) == (1, "best match: Frontend Developer Intern")
    assert 'Job title matches your target role "Frontend Developer Intern"' in (
        result.positive_reasons
    )


def test_role_partial_at_least_half_is_positive() -> None:
    result = match(MatchProfile(target_roles=("Backend Engineer",)), title="Software Engineer")
    assert factor(result, FactorKey.ROLE_SIMILARITY).ratio == Fraction(1, 2)
    assert 'Job title partially matches your target role "Backend Engineer"' in (
        result.positive_reasons
    )


def test_role_partial_below_half_is_negative() -> None:
    profile = MatchProfile(target_roles=("Machine Learning Engineer",))
    result = match(profile, title="Software Engineer")
    assert factor(result, FactorKey.ROLE_SIMILARITY).ratio == Fraction(1, 3)
    assert 'Job title partially matches your target role "Machine Learning Engineer"' in (
        result.negative_reasons
    )


def test_role_no_shared_terms_emits_negative_template() -> None:
    result = match(MatchProfile(target_roles=("Data Analyst",)), title="Software Engineer")
    assert factor(result, FactorKey.ROLE_SIMILARITY).ratio == 0
    assert "Job title does not match your target roles" in result.negative_reasons


def test_role_best_role_uses_max_ratio_then_casefold_order() -> None:
    profile = MatchProfile(target_roles=("software tester", "Data Engineer", "backend engineer"))
    result = match(profile, title="Software Engineer")
    # All three score 1/2; "backend engineer" is smallest after casefold.
    assert factor(result, FactorKey.ROLE_SIMILARITY).detail == "best match: backend engineer"


def test_role_stop_tokens_match_design_list() -> None:
    design_list = (
        "intern, internship, trainee, junior, jr, senior, sr, lead, principal, staff, graduate, "
        "grad, new, entry, level, associate, i, ii, iii, the, and, of, for, a, an, to, in, at, "
        "with, remote, hybrid, onsite, m, f, d, w"
    )
    assert frozenset(design_list.split(", ")) == ROLE_STOP_TOKENS


def test_role_tokens_map_synonyms_and_expand_swe() -> None:
    assert role_tokens("SWE Intern") == {"software", "engineer"}
    assert role_tokens("Full Stack Dev II") == {"fullstack", "engineer"}
    assert role_tokens("C++/C# Programmer (m/f/d)") == {"c++", "c#", "engineer"}


# ---------- 4. experience ----------


def test_experience_unknown_user_level_neutral() -> None:
    result = match(experience_level=ExperienceLevel.JUNIOR)
    experience = factor(result, FactorKey.EXPERIENCE)
    assert experience.ratio == Fraction(1, 2)
    assert "Experience level not specified" in result.negative_reasons


def test_experience_unknown_job_level_neutral() -> None:
    result = match(MatchProfile(experience_level=ExperienceLevel.ENTRY))
    assert factor(result, FactorKey.EXPERIENCE).ratio == Fraction(1, 2)


def test_experience_user_at_or_above_job_full_credit() -> None:
    profile = MatchProfile(experience_level=ExperienceLevel.ENTRY)
    result = match(profile, experience_level=ExperienceLevel.INTERNSHIP)
    assert factor(result, FactorKey.EXPERIENCE).points == 15
    assert "Your entry experience meets the internship level" in result.positive_reasons


def test_experience_gap_one_gives_three_fifths() -> None:
    profile = MatchProfile(experience_level=ExperienceLevel.ENTRY)
    result = match(profile, experience_level=ExperienceLevel.JUNIOR)
    assert factor(result, FactorKey.EXPERIENCE).ratio == Fraction(3, 5)
    assert "Role expects junior level; your profile is entry" in result.negative_reasons


def test_experience_gap_two_gives_one_fifth() -> None:
    profile = MatchProfile(experience_level=ExperienceLevel.ENTRY)
    result = match(profile, experience_level=ExperienceLevel.MID)
    assert factor(result, FactorKey.EXPERIENCE).ratio == Fraction(1, 5)


def test_experience_gap_three_or_more_gives_zero() -> None:
    profile = MatchProfile(experience_level=ExperienceLevel.INTERNSHIP)
    result = match(profile, experience_level=ExperienceLevel.MID)
    assert factor(result, FactorKey.EXPERIENCE).ratio == 0
    assert "Role expects mid level, well above your internship level" in result.negative_reasons


# ---------- 5. location ----------


def test_location_remote_job_full_credit() -> None:
    result = match(work_mode=WorkMode.REMOTE, location="Anywhere")
    assert factor(result, FactorKey.LOCATION).ratio == 1
    assert "Remote role, location-independent" in result.positive_reasons


def test_location_no_candidates_neutral() -> None:
    result = match(MatchProfile(location="  ", preferred_locations=(",",)))
    assert factor(result, FactorKey.LOCATION).ratio == Fraction(1, 2)
    assert "Add a location or preferred locations to your profile" in result.negative_reasons


def test_location_first_segment_match_full_credit() -> None:
    result = match(MatchProfile(location="  berlin ,  GERMANY"))
    assert factor(result, FactorKey.LOCATION).ratio == 1
    assert "Berlin, Germany matches your location or preferred locations" in (
        result.positive_reasons
    )


def test_location_preferred_location_counts_as_candidate() -> None:
    profile = MatchProfile(location="Paris, France", preferred_locations=("Berlin",))
    assert factor(match(profile), FactorKey.LOCATION).ratio == 1


def test_location_same_country_gives_half() -> None:
    result = match(MatchProfile(location="Munich, Germany"))
    assert factor(result, FactorKey.LOCATION).ratio == Fraction(1, 2)
    assert "Berlin, Germany is in a country you prefer" in result.positive_reasons


def test_location_mismatch_gives_zero() -> None:
    result = match(MatchProfile(location="Paris, France"))
    assert factor(result, FactorKey.LOCATION).ratio == 0
    assert "Berlin, Germany is outside your preferred locations" in result.negative_reasons


def test_location_job_without_segments_gives_zero() -> None:
    result = match(MatchProfile(location="Berlin"), location=" , ")
    assert factor(result, FactorKey.LOCATION).ratio == 0


def test_location_segments_casefold_collapse_and_drop_empty() -> None:
    assert location_segments(" New   York ,, USA ") == ("new york", "usa")


# ---------- 6. work mode ----------


def test_work_mode_no_preference_neutral() -> None:
    result = match()
    assert factor(result, FactorKey.WORK_MODE).ratio == Fraction(1, 2)
    assert "Add preferred work modes to your profile" in result.negative_reasons


def test_work_mode_preferred_full_credit() -> None:
    result = match(MatchProfile(preferred_work_modes=(WorkMode.ONSITE,)))
    assert factor(result, FactorKey.WORK_MODE).points == 5
    assert "Onsite work matches your preference" in result.positive_reasons


def test_work_mode_hybrid_not_preferred_gives_half() -> None:
    result = match(MatchProfile(preferred_work_modes=(WorkMode.REMOTE,)), work_mode=WorkMode.HYBRID)
    assert factor(result, FactorKey.WORK_MODE).ratio == Fraction(1, 2)
    assert "Hybrid work partially matches your preference" in result.positive_reasons


def test_work_mode_not_preferred_gives_zero() -> None:
    result = match(MatchProfile(preferred_work_modes=(WorkMode.REMOTE,)))
    assert factor(result, FactorKey.WORK_MODE).ratio == 0
    assert "Onsite work does not match your preferred work modes" in result.negative_reasons


# ---------- 7. education ----------


def test_education_no_requirement_full_credit() -> None:
    result = match()
    assert factor(result, FactorKey.EDUCATION).ratio == 1
    assert "No minimum education requirement" in result.positive_reasons


def test_education_unknown_user_neutral() -> None:
    result = match(min_education_level=EducationLevel.BACHELOR)
    assert factor(result, FactorKey.EDUCATION).ratio == Fraction(1, 2)
    assert "Education level not specified in your profile" in result.negative_reasons


def test_education_meets_requirement_full_credit() -> None:
    profile = MatchProfile(education_level=EducationLevel.PHD)
    result = match(profile, min_education_level=EducationLevel.MASTER)
    assert factor(result, FactorKey.EDUCATION).ratio == 1
    assert "Your education meets the master's requirement" in result.positive_reasons


def test_education_one_level_below_gives_half() -> None:
    profile = MatchProfile(education_level=EducationLevel.MASTER)
    result = match(profile, min_education_level=EducationLevel.PHD)
    assert factor(result, FactorKey.EDUCATION).ratio == Fraction(1, 2)
    assert "Role prefers PhD; you are one level below" in result.negative_reasons


def test_education_two_levels_below_gives_zero() -> None:
    profile = MatchProfile(education_level=EducationLevel.HIGH_SCHOOL)
    result = match(profile, min_education_level=EducationLevel.BACHELOR)
    assert factor(result, FactorKey.EDUCATION).ratio == 0
    assert "Role requires bachelor's education" in result.negative_reasons


# ---------- 8. projects ----------


def project(name: str, *technologies: str) -> ProjectInput:
    return ProjectInput(name=name, technologies=technologies)


def test_projects_job_without_skills_neutral() -> None:
    result = match(MatchProfile(projects=(project("Site", "React"),)))
    assert factor(result, FactorKey.PROJECTS).ratio == Fraction(1, 2)
    assert "Role lists no skills to compare projects against" in result.negative_reasons


def test_projects_none_relevant_gives_zero() -> None:
    result = match(MatchProfile(projects=(project("Site", "Vue"),)), required_skills=("React",))
    assert factor(result, FactorKey.PROJECTS).ratio == 0
    assert "No projects demonstrate this role's skills" in result.negative_reasons


def test_projects_one_relevant_gives_three_fifths() -> None:
    profile = MatchProfile(projects=(project("Portfolio", "reactjs", "TypeScript"),))
    result = match(profile, required_skills=("React", "TypeScript"))
    projects = factor(result, FactorKey.PROJECTS)
    assert (projects.ratio, projects.points) == (Fraction(3, 5), 3)
    assert 'Project "Portfolio" uses React' in result.positive_reasons


def test_projects_two_relevant_full_credit_with_more_suffix() -> None:
    profile = MatchProfile(projects=(project("Zeta", "React"), project("Alpha", "Docker")))
    result = match(profile, required_skills=("React",), preferred_skills=("Docker",))
    assert factor(result, FactorKey.PROJECTS).ratio == 1
    assert 'Project "Alpha" uses Docker (+1 more relevant projects)' in result.positive_reasons


def test_projects_casefold_duplicate_names_form_one_group() -> None:
    profile = MatchProfile(projects=(project("site", "React"), project(" Site ", "React")))
    result = match(profile, required_skills=("React",))
    assert factor(result, FactorKey.PROJECTS).ratio == Fraction(3, 5)
    assert 'Project "Site" uses React' in result.positive_reasons


def test_projects_blank_names_are_skipped() -> None:
    result = match(MatchProfile(projects=(project("  ", "React"),)), required_skills=("React",))
    assert factor(result, FactorKey.PROJECTS).ratio == 0


def test_projects_ignore_technical_skills() -> None:
    profile = MatchProfile(technical_skills=("React",))
    result = match(profile, required_skills=("React",))
    assert factor(result, FactorKey.PROJECTS).ratio == 0
