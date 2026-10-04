"""Unit tests for `ProfileUpdate` validation (R1.3-R1.5, design.md §8.1)."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.schemas.common import WorkMode, format_utc
from app.schemas.profile import ProfileUpdate

pytestmark = pytest.mark.unit

VALID: dict[str, object] = {"name": "Demo Student", "email": "demo@internpilot.dev"}


def build(**overrides: object) -> ProfileUpdate:
    return ProfileUpdate.model_validate({**VALID, **overrides})


def error_locs(**overrides: object) -> list[tuple[int | str, ...]]:
    with pytest.raises(ValidationError) as excinfo:
        build(**overrides)
    return [error["loc"] for error in excinfo.value.errors()]


def test_profile_update_minimal_payload_defaults_to_empty_profile() -> None:
    profile = build()

    assert profile.location is None
    assert profile.target_roles == []
    assert profile.technical_skills == []
    assert profile.resume_text == ""
    assert profile.github_url is None


def test_profile_update_name_is_trimmed() -> None:
    assert build(name="  Ada Lovelace  ").name == "Ada Lovelace"


@pytest.mark.parametrize("name", ["", "   ", "x" * 101])
def test_profile_update_name_blank_or_too_long_rejected(name: str) -> None:
    assert error_locs(name=name) == [("name",)]


def test_profile_update_missing_name_and_email_rejected() -> None:
    with pytest.raises(ValidationError) as excinfo:
        ProfileUpdate.model_validate({})

    assert {error["loc"] for error in excinfo.value.errors()} == {("name",), ("email",)}


def test_profile_update_email_is_lowercased() -> None:
    assert build(email="Demo@InternPilot.DEV").email == "demo@internpilot.dev"


@pytest.mark.parametrize("email", ["not-an-email", "a@b@c.dev", "x" * 250 + "@internpilot.dev"])
def test_profile_update_invalid_email_rejected(email: str) -> None:
    assert error_locs(email=email) == [("email",)]


def test_profile_update_extra_field_forbidden() -> None:
    assert error_locs(seed_key="demo") == [("seed_key",)]


def test_profile_update_nested_extra_field_forbidden() -> None:
    locs = error_locs(projects=[{"name": "Tracker", "stars": 5}])

    assert locs == [("projects", 0, "stars")]


def test_profile_update_location_too_long_rejected() -> None:
    assert error_locs(location="x" * 121) == [("location",)]


def test_profile_update_blank_optional_text_becomes_none() -> None:
    profile = build(location="  ", portfolio_url="")

    assert profile.location is None
    assert profile.portfolio_url is None


def test_profile_update_target_roles_trimmed_and_deduped_case_insensitively() -> None:
    profile = build(target_roles=[" Frontend Engineer ", "frontend engineer", "Data Analyst"])

    assert profile.target_roles == ["Frontend Engineer", "Data Analyst"]


def test_profile_update_target_roles_too_many_rejected() -> None:
    assert error_locs(target_roles=[f"Role {i}" for i in range(11)]) == [("target_roles",)]


def test_profile_update_preferred_location_item_too_long_rejected() -> None:
    assert error_locs(preferred_locations=["x" * 81]) == [("preferred_locations", 0)]


def test_profile_update_work_modes_parsed_as_enum() -> None:
    profile = build(preferred_work_modes=["remote", "hybrid"])

    assert profile.preferred_work_modes == [WorkMode.REMOTE, WorkMode.HYBRID]


def test_profile_update_duplicate_work_modes_rejected() -> None:
    assert error_locs(preferred_work_modes=["remote", "remote"]) == [("preferred_work_modes",)]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("preferred_work_modes", ["anywhere"]),
        ("experience_level", "expert"),
        ("education_level", "Bachelor"),
    ],
)
def test_profile_update_invalid_enum_rejected(field: str, value: object) -> None:
    locs = error_locs(**{field: value})

    assert locs[0][0] == field


def test_profile_update_education_valid_entry_accepted() -> None:
    entry = {"institution": "State University", "degree": "BSc", "start_year": 2021}

    assert build(education=[entry]).education[0].end_year is None


def test_profile_update_education_start_after_end_rejected() -> None:
    entry = {"institution": "State University", "start_year": 2024, "end_year": 2020}

    assert error_locs(education=[entry]) == [("education", 0)]


@pytest.mark.parametrize("year", [1949, 2101])
def test_profile_update_education_year_out_of_range_rejected(year: int) -> None:
    locs = error_locs(education=[{"institution": "State University", "end_year": year}])

    assert locs == [("education", 0, "end_year")]


def test_profile_update_education_too_many_entries_rejected() -> None:
    entries = [{"institution": f"School {i}"} for i in range(11)]

    assert error_locs(education=entries) == [("education",)]


def test_profile_update_technical_skills_too_many_rejected() -> None:
    assert error_locs(technical_skills=[f"skill{i}" for i in range(101)]) == [("technical_skills",)]


def test_profile_update_technical_skill_too_long_rejected() -> None:
    assert error_locs(technical_skills=["Python", "x" * 51]) == [("technical_skills", 1)]


def test_profile_update_technical_skill_only_punctuation_rejected_at_index() -> None:
    assert error_locs(technical_skills=["React", "(,)"]) == [("technical_skills", 1)]


def test_profile_update_soft_skills_too_many_rejected() -> None:
    assert error_locs(soft_skills=[f"skill {i}" for i in range(51)]) == [("soft_skills",)]


def test_profile_update_project_limits_enforced() -> None:
    project = {"name": "Tracker", "description": "x" * 2001, "technologies": ["x"] * 21}

    locs = error_locs(projects=[project])

    assert set(locs) == {("projects", 0, "description"), ("projects", 0, "technologies")}


def test_profile_update_too_many_projects_rejected() -> None:
    assert error_locs(projects=[{"name": f"P{i}"} for i in range(21)]) == [("projects",)]


def test_profile_update_certification_limits_enforced() -> None:
    cert = {"name": "x" * 121, "issuer": "Cloud Co", "year": 1900}

    locs = error_locs(certifications=[cert])

    assert set(locs) == {("certifications", 0, "name"), ("certifications", 0, "year")}


def test_profile_update_too_many_certifications_rejected() -> None:
    assert error_locs(certifications=[{"name": f"C{i}"} for i in range(31)]) == [
        ("certifications",)
    ]


def test_profile_update_resume_text_too_long_rejected() -> None:
    assert error_locs(resume_text="x" * 50_001) == [("resume_text",)]


def test_profile_update_valid_urls_accepted() -> None:
    profile = build(
        github_url="https://github.com/demo",
        linkedin_url="https://www.linkedin.com/in/demo",
        portfolio_url="http://demo.example.com/portfolio",
        projects=[{"name": "Tracker", "url": "https://tracker.example.com"}],
    )

    assert profile.github_url == "https://github.com/demo"
    assert profile.linkedin_url == "https://www.linkedin.com/in/demo"
    assert profile.projects[0].url == "https://tracker.example.com"


@pytest.mark.parametrize(
    "url",
    [
        "ftp://demo.example.com",
        "javascript:alert(1)",
        "demo.example.com",
        "https://",
        "https://user:pass@demo.example.com",
        "https://demo.example.com/a b",
        "https://demo.example.com:99999",
        "https://demo.example.com/" + "x" * 300,
    ],
)
def test_profile_update_invalid_portfolio_url_rejected(url: str) -> None:
    assert error_locs(portfolio_url=url) == [("portfolio_url",)]


def test_profile_update_project_url_bad_scheme_rejected() -> None:
    locs = error_locs(projects=[{"name": "Tracker", "url": "file:///etc/passwd"}])

    assert locs == [("projects", 0, "url")]


@pytest.mark.parametrize(
    "url",
    ["https://gitlab.com/demo", "https://github.com.evil.dev/demo", "https://api.github.com/x"],
)
def test_profile_update_github_url_wrong_host_rejected(url: str) -> None:
    assert error_locs(github_url=url) == [("github_url",)]


@pytest.mark.parametrize("url", ["https://linkedin.example.com/in/demo", "https://lnkd.in/demo"])
def test_profile_update_linkedin_url_wrong_host_rejected(url: str) -> None:
    assert error_locs(linkedin_url=url) == [("linkedin_url",)]


def test_profile_update_error_messages_do_not_echo_input() -> None:
    url_with_credentials = "https://user:placeholder@github.com/demo"
    with pytest.raises(ValidationError) as excinfo:
        build(github_url=url_with_credentials)

    assert all(url_with_credentials not in error["msg"] for error in excinfo.value.errors())


def test_format_utc_uses_z_suffix() -> None:
    assert format_utc(datetime(2025, 1, 15, 9, 30, tzinfo=UTC)) == "2025-01-15T09:30:00Z"
