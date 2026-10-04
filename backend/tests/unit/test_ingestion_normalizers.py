"""Unit tests for ingestion normalizers and fingerprints (R10.4, design.md §11.3, §11.4)."""

from datetime import date

import pytest

from app.schemas.common import JobSource
from app.schemas.ingest import DESCRIPTION_MAX_LENGTH, JobCreate, RawFormat
from app.services.ingestion.normalizers import (
    Rejection,
    arbeitnow_employment_type,
    catalog_skills_in,
    fingerprint,
    html_to_text,
    infer_experience_level,
    normalize_item,
    remotive_employment_type,
)

pytestmark = pytest.mark.unit

TODAY = date(2025, 1, 15)


def remotive_item(**overrides: object) -> dict[str, object]:
    item: dict[str, object] = {
        "id": 1001,
        "url": "https://remotive.com/remote-jobs/software-dev/frontend-1001",
        "title": "Frontend Developer",
        "company_name": "Acme &amp; Co",
        "job_type": "full_time",
        "candidate_required_location": "Europe",
        "tags": ["React", "TypeScript", "reactjs"],
        "description": "<p>Build UIs with <b>React</b>.</p><p>Python and Docker are a plus.</p>",
    }
    item.update(overrides)
    return item


def arbeitnow_item(**overrides: object) -> dict[str, object]:
    item: dict[str, object] = {
        "slug": "backend-engineer-berlin-123",
        "company_name": "Beispiel GmbH",
        "title": "Backend Engineer",
        "description": "<div>We use Python and PostgreSQL.</div>",
        "remote": False,
        "url": "https://www.arbeitnow.com/jobs/backend-engineer-berlin-123",
        "tags": ["Python"],
        "job_types": ["Full Time"],
        "location": "Berlin",
    }
    item.update(overrides)
    return item


def normalized_item(**overrides: object) -> dict[str, object]:
    item: dict[str, object] = {
        "external_id": "seed-001",
        "title": "Data Analyst",
        "company": "Example Co",
        "location": "Bengaluru",
        "employment_type": "full_time",
        "work_mode": "hybrid",
        "description": "Analyse data.",
        "application_url": "https://jobs.example.com/1",
        "required_skills": ["SQL", "Python"],
        "preferred_skills": ["Tableau"],
        "salary_min": 100,
        "salary_max": 200,
        "salary_currency": "INR",
        "salary_period": "month",
        "deadline_in_days": 10,
    }
    item.update(overrides)
    return item


def normalize(
    raw: object, raw_format: RawFormat, source: JobSource = JobSource.PAYLOAD
) -> JobCreate | Rejection:
    return normalize_item(raw, raw_format, source, TODAY, 0)


def accepted(raw: object, raw_format: RawFormat) -> JobCreate:
    result = normalize(raw, raw_format)
    assert isinstance(result, JobCreate), result
    return result


def rejected(raw: object, raw_format: RawFormat) -> Rejection:
    result = normalize(raw, raw_format)
    assert isinstance(result, Rejection), result
    return result


def test_html_to_text_strips_tags_unescapes_entities_and_collapses_whitespace() -> None:
    markup = "<h1>Hello&nbsp;&amp; welcome</h1>\n\n<p>to   the<br>team</p>"
    assert html_to_text(markup) == "Hello & welcome to the team"


def test_html_to_text_drops_script_and_style_content() -> None:
    markup = "<style>p{}</style><p>Visible</p><script>alert('x')</script>"
    assert html_to_text(markup) == "Visible"


def test_remotive_item_maps_fields_and_skills() -> None:
    job = accepted(remotive_item(), RawFormat.REMOTIVE)
    assert job.external_id == "1001"
    assert job.company == "Acme & Co"
    assert job.location == "Europe"
    assert job.work_mode == "remote"
    assert job.employment_type == "full_time"
    assert job.description == "Build UIs with React. Python and Docker are a plus."
    assert job.required_skills == ["react", "typescript"]
    assert job.preferred_skills == ["docker", "python"]


def test_remotive_item_without_location_defaults_to_remote() -> None:
    job = accepted(remotive_item(candidate_required_location=""), RawFormat.REMOTIVE)
    assert job.location == "Remote"


@pytest.mark.parametrize(
    ("job_type", "expected"),
    [
        ("full_time", "full_time"),
        ("part_time", "part_time"),
        ("contract", "contract"),
        ("freelance", "contract"),
        ("internship", "internship"),
        ("other", "full_time"),
        (None, "full_time"),
    ],
)
def test_remotive_employment_type_mapping(job_type: object, expected: str) -> None:
    assert remotive_employment_type(job_type) == expected


@pytest.mark.parametrize(
    ("job_types", "expected"),
    [
        (["Internship / Praktikum"], "internship"),
        (["Part Time"], "part_time"),
        (["Contract"], "contract"),
        (["Freelance"], "contract"),
        (["Full Time"], "full_time"),
        ([], "full_time"),
    ],
)
def test_arbeitnow_employment_type_mapping(job_types: list[str], expected: str) -> None:
    assert arbeitnow_employment_type(job_types) == expected


def test_arbeitnow_item_maps_slug_work_mode_and_skills() -> None:
    job = accepted(arbeitnow_item(), RawFormat.ARBEITNOW)
    assert job.external_id == "backend-engineer-berlin-123"
    assert job.work_mode == "onsite"
    assert job.required_skills == ["python"]
    assert job.preferred_skills == ["postgresql"]


def test_arbeitnow_remote_item_is_remote() -> None:
    job = accepted(arbeitnow_item(remote=True, location=""), RawFormat.ARBEITNOW)
    assert job.work_mode == "remote"
    assert job.location == "Remote"


def test_normalized_item_resolves_deadline_in_days_against_today() -> None:
    job = accepted(normalized_item(), RawFormat.NORMALIZED)
    assert job.deadline == date(2025, 1, 25)
    assert job.required_skills == ["sql", "python"]
    assert job.salary_currency == "INR"


def test_normalized_item_explicit_deadline_wins() -> None:
    job = accepted(normalized_item(deadline="2025-03-01"), RawFormat.NORMALIZED)
    assert job.deadline == date(2025, 3, 1)


def test_normalized_item_non_integer_deadline_in_days_is_rejected() -> None:
    rejection = rejected(normalized_item(deadline_in_days="soon"), RawFormat.NORMALIZED)
    assert rejection.reason == "deadline_in_days: must be an integer"


def test_intern_title_forces_internship_and_infers_level() -> None:
    job = accepted(normalized_item(title="Software Engineering Intern"), RawFormat.NORMALIZED)
    assert job.employment_type == "internship"
    assert job.experience_level == "internship"


def test_internal_title_is_not_an_internship() -> None:
    job = accepted(normalized_item(title="Internal Tools Engineer"), RawFormat.NORMALIZED)
    assert job.employment_type == "full_time"
    assert job.experience_level is None


def test_explicit_experience_level_is_kept() -> None:
    job = accepted(
        normalized_item(title="Senior Engineer", experience_level="mid"), RawFormat.NORMALIZED
    )
    assert job.experience_level == "mid"


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Data Science Trainee", "internship"),
        ("Graduate Software Engineer", "entry"),
        ("New Grad Backend Engineer", "entry"),
        ("Jr. Developer", "junior"),
        ("Mid-level Engineer", "mid"),
        ("Staff Engineer", "senior"),
        ("Software Engineer", None),
    ],
)
def test_infer_experience_level_from_title(title: str, expected: str | None) -> None:
    assert infer_experience_level(title) == expected


def test_description_is_truncated_to_maximum_length() -> None:
    long_html = "<p>" + "a" * (DESCRIPTION_MAX_LENGTH + 500) + "</p>"
    job = accepted(normalized_item(description=long_html), RawFormat.NORMALIZED)
    assert len(job.description) == DESCRIPTION_MAX_LENGTH


def test_tags_are_capped_at_fifteen_skills() -> None:
    tags = [f"skill{number}" for number in range(20)]
    job = accepted(remotive_item(tags=tags), RawFormat.REMOTIVE)
    assert len(job.required_skills) == 15


def test_catalog_skills_in_respects_word_boundaries_and_ambiguous_terms() -> None:
    assert catalog_skills_in("We write Java, not JavaScript? go to market") == {
        "java",
        "javascript",
    }
    assert catalog_skills_in("Services in Go and R") >= {"go", "r"}


def test_missing_title_is_rejected_with_field_reason() -> None:
    rejection = rejected(remotive_item(title=None), RawFormat.REMOTIVE)
    assert rejection.reason.startswith("title:")


def test_bad_url_is_rejected_without_echoing_input() -> None:
    rejection = rejected(
        normalized_item(application_url="ftp://secret-host/x"), RawFormat.NORMALIZED
    )
    assert "application_url" in rejection.reason
    assert "secret-host" not in rejection.reason


def test_salary_min_above_max_is_rejected() -> None:
    rejection = rejected(normalized_item(salary_min=300, salary_max=200), RawFormat.NORMALIZED)
    assert "salary_min must not exceed salary_max" in rejection.reason


def test_non_object_item_is_rejected() -> None:
    assert rejected("not a job", RawFormat.NORMALIZED).reason == "item: must be a JSON object"


def test_fingerprint_ignores_case_punctuation_and_spacing() -> None:
    first = fingerprint("Frontend  Intern", "Acme, Inc.", "Remote")
    second = fingerprint("frontend-intern", "ACME Inc", " remote ")
    assert first == second
    assert len(first) == 64


def test_fingerprint_differs_when_location_differs() -> None:
    assert fingerprint("Intern", "Acme", "Berlin") != fingerprint("Intern", "Acme", "Paris")
