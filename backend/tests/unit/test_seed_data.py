"""The repository seed files and their contracts (R11.1, R11.3, design.md §12)."""

import json
import shutil
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import DEFAULT_DATA_DIR
from app.core.errors import SeedDataError
from app.schemas.common import JobSource
from app.schemas.ingest import JobCreate, RawFormat
from app.schemas.seed import SeedApplication, SeedJob, SeedJobs, parse_seed_profile
from app.services.application_status import ApplicationStatus
from app.services.ingestion.normalizers import fingerprint, normalize_item
from app.services.matching.normalization import normalize_skill
from app.services.matching.skill_catalog import CATALOG
from app.services.seed_service import (
    SEED_APPLICATIONS_FILE,
    SEED_PROFILE_FILE,
    SeedData,
    load_seed_data,
    seed_application_create,
)

pytestmark = pytest.mark.unit

DEMO_NAME = "Demo Student"
DEMO_EMAIL = "demo@internpilot.dev"
TODAY = date(2025, 1, 15)
SEED_JOBS_PATH = DEFAULT_DATA_DIR / "seed_jobs.json"
REMOTIVE_SAMPLE_PATH = DEFAULT_DATA_DIR / "ingest" / "remotive_sample.json"


def read(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def seed() -> SeedData:
    return load_seed_data(DEFAULT_DATA_DIR, DEMO_NAME, DEMO_EMAIL)


def raw_seed_skills() -> list[str]:
    profile = read(DEFAULT_DATA_DIR / SEED_PROFILE_FILE)
    jobs = read(SEED_JOBS_PATH)
    assert isinstance(profile, dict)
    assert isinstance(jobs, list)
    names = list(profile["technical_skills"])
    names += [tech for project in profile["projects"] for tech in project["technologies"]]
    names += [skill for job in jobs for skill in job["required_skills"] + job["preferred_skills"]]
    return names


def test_seed_files_validate_with_configured_identity(seed: SeedData) -> None:
    assert (seed.profile.name, seed.profile.email) == (DEMO_NAME, DEMO_EMAIL)


@pytest.mark.parametrize("raw", sorted(set(raw_seed_skills())))
def test_seed_skill_normalizes_to_catalog_key(raw: str) -> None:
    assert normalize_skill(raw) in CATALOG


def test_seed_data_meets_r11_1_volume_and_variety(seed: SeedData) -> None:
    assert len(seed.skill_names()) >= 20
    assert len(seed.profile.technical_skills) >= 20
    assert len(seed.jobs) >= 30
    assert {"internship", "full_time"} <= {job.employment_type for job in seed.jobs}
    assert {job.work_mode for job in seed.jobs} == {"remote", "hybrid", "onsite"}
    assert len({job.experience_level for job in seed.jobs}) == 5
    assert len({job.company for job in seed.jobs}) >= 15
    assert len({job.location for job in seed.jobs}) >= 8
    assert len(seed.applications) >= 10
    assert len({application.status for application in seed.applications}) >= 6


def test_seed_deadlines_are_relative_with_upcoming_and_open_ended_jobs(seed: SeedData) -> None:
    days = [job.deadline_in_days for job in seed.jobs]
    assert sum(1 for value in days if value is not None and 0 <= value <= 14) >= 5
    assert days.count(None) >= 2
    assert all("deadline" not in item for item in read(SEED_JOBS_PATH))


def test_seed_job_fingerprints_are_unique(seed: SeedData) -> None:
    prints = {fingerprint(job.title, job.company, job.location) for job in seed.jobs}
    assert len(prints) == len(seed.jobs)


def test_seed_jobs_normalize_without_changing_declared_fields(seed: SeedData) -> None:
    for index, job in enumerate(seed.jobs):
        item = job.model_dump(mode="json", exclude_none=True)
        result = normalize_item(item, RawFormat.NORMALIZED, JobSource.SEED, TODAY, index)
        assert isinstance(result, JobCreate), result
        assert (result.employment_type, result.experience_level) == (
            job.employment_type,
            job.experience_level,
        )


def test_seed_contact_data_uses_placeholder_domains(seed: SeedData) -> None:
    emails = [app.recruiter_email for app in seed.applications if app.recruiter_email]
    assert emails
    assert all(email.endswith(("@example.com", "@example.org")) for email in emails)
    assert all(".example.com/" in job.application_url for job in seed.jobs)


def test_ingest_fixture_sample_does_not_collide_with_seed_jobs(seed: SeedData) -> None:
    document = read(REMOTIVE_SAMPLE_PATH)
    assert isinstance(document, dict)
    seed_prints = {fingerprint(job.title, job.company, job.location) for job in seed.jobs}
    for index, raw in enumerate(document["jobs"]):
        result = normalize_item(raw, RawFormat.REMOTIVE, JobSource.FIXTURE, TODAY, index)
        assert isinstance(result, JobCreate), result
        assert fingerprint(result.title, result.company, result.location) not in seed_prints


def test_seed_application_create_resolves_relative_dates() -> None:
    item = SeedApplication(
        job_external_id="seed-001",
        status=ApplicationStatus.INTERVIEW,
        applied_days_ago=12,
        deadline_in_days=2,
        interview_in_days=3,
    )

    created = seed_application_create(item, job_id=7, today=TODAY)

    assert created.applied_at == date(2025, 1, 3)
    assert created.deadline == date(2025, 1, 17)
    assert created.interview_date == datetime(2025, 1, 18, 10, 0, tzinfo=UTC)


def test_seed_application_submitted_status_requires_applied_days_ago() -> None:
    with pytest.raises(ValidationError, match="applied_days_ago is required"):
        SeedApplication(job_external_id="seed-001", status=ApplicationStatus.APPLIED)


def test_seed_application_saved_status_rejects_applied_days_ago() -> None:
    with pytest.raises(ValidationError, match="not allowed"):
        SeedApplication(
            job_external_id="seed-001", status=ApplicationStatus.SAVED, applied_days_ago=1
        )


def test_seed_job_unknown_field_is_rejected() -> None:
    item = read(SEED_JOBS_PATH)[0]
    with pytest.raises(ValidationError, match="extra"):
        SeedJob.model_validate({**item, "deadline": "2025-01-20"})


def test_seed_jobs_duplicate_external_id_is_rejected() -> None:
    item = read(SEED_JOBS_PATH)[0]
    with pytest.raises(ValidationError, match="unique"):
        SeedJobs.model_validate([item, {**item, "title": "Another Title"}])


def test_seed_profile_must_not_set_identity_fields() -> None:
    with pytest.raises(ValueError, match="must not set email"):
        parse_seed_profile({"email": "someone@example.com"}, DEMO_NAME, DEMO_EMAIL)


def test_load_seed_data_missing_file_raises_seed_data_error(tmp_path: Path) -> None:
    with pytest.raises(SeedDataError, match="seed_profile.json: file not found"):
        load_seed_data(tmp_path, DEMO_NAME, DEMO_EMAIL)


def test_load_seed_data_unknown_job_reference_raises_seed_data_error(tmp_path: Path) -> None:
    for name in (SEED_PROFILE_FILE, "seed_jobs.json"):
        shutil.copy(DEFAULT_DATA_DIR / name, tmp_path / name)
    applications = [{"job_external_id": "seed-999", "status": "Saved"}]
    (tmp_path / SEED_APPLICATIONS_FILE).write_text(json.dumps(applications), encoding="utf-8")

    with pytest.raises(SeedDataError, match="unknown job_external_id"):
        load_seed_data(tmp_path, DEMO_NAME, DEMO_EMAIL)
