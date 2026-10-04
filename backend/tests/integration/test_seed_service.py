"""Integration tests for `SeedService` on the repository seed files (R11.1-R11.3, §12)."""

import json
import shutil
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.clock import FixedClock
from app.core.config import DEFAULT_DATA_DIR, Settings, get_settings
from app.core.errors import EmailTakenError, SeedDataError
from app.models import ActivityEvent, Application, Job, Skill, User
from app.repositories.user_repository import UserRepository
from app.schemas.application import ApplicationUpdate
from app.schemas.ingest import IngestRequest
from app.schemas.profile import ProfileUpdate
from app.services.application_service import ApplicationService
from app.services.application_status import ApplicationStatus
from app.services.ingestion.service import IngestionService, default_sources
from app.services.profile_service import ProfileService
from app.services.seed_service import SeedService, SeedSummary

pytestmark = pytest.mark.integration

DEMO_EMAIL = "demo@internpilot.dev"


@pytest.fixture
def settings() -> Settings:
    return get_settings().model_copy(update={"data_dir": DEFAULT_DATA_DIR})


@pytest.fixture
def run_seed(
    db_session: Session, fixed_clock: FixedClock, settings: Settings
) -> Callable[..., SeedSummary]:
    def run(clock: FixedClock = fixed_clock, config: Settings = settings) -> SeedSummary:
        return SeedService(db_session, clock, config).run()

    return run


def count(session: Session, model: type[object]) -> int:
    return session.scalar(sa.select(sa.func.count()).select_from(model)) or 0


def demo_user(session: Session) -> User:
    user = UserRepository(session).get_by_seed_key("demo")
    assert user is not None
    return user


def seed_job(session: Session, external_id: str) -> Job:
    return session.scalars(
        sa.select(Job).where(Job.source == "seed", Job.external_id == external_id)
    ).one()


def application_for(session: Session, external_id: str) -> Application:
    job = seed_job(session, external_id)
    return session.scalars(sa.select(Application).where(Application.job_id == job.id)).one()


def table_counts(session: Session) -> tuple[int, ...]:
    return tuple(count(session, model) for model in (User, Skill, Job, Application))


def test_seed_loads_r11_1_dataset(
    db_session: Session, run_seed: Callable[..., SeedSummary]
) -> None:
    summary = run_seed()

    user = demo_user(db_session)
    statuses = set(db_session.scalars(sa.select(Application.status)))
    sources = set(db_session.scalars(sa.select(Job.source)))
    assert (count(db_session, User), user.email, user.name) == (1, DEMO_EMAIL, "Demo Student")
    assert len(UserRepository(db_session).list_skills(user.id)) >= 20
    assert count(db_session, Skill) >= 20
    assert count(db_session, Job) >= 30
    assert sources == {"seed"}
    assert count(db_session, Application) >= 10
    assert len(statuses) >= 6
    assert summary.user_created
    assert summary.jobs_created == count(db_session, Job)
    assert summary.applications_created == count(db_session, Application)
    assert summary.applications_skipped == 0
    assert user.projects and user.education and user.resume_text


def test_seed_records_application_created_events(
    db_session: Session, run_seed: Callable[..., SeedSummary]
) -> None:
    run_seed()

    types = list(db_session.scalars(sa.select(ActivityEvent.type)))
    assert types.count("application_created") == count(db_session, Application)
    assert types.count("jobs_ingested") == 1


def test_seed_twice_creates_no_duplicates(
    db_session: Session, run_seed: Callable[..., SeedSummary]
) -> None:
    first = run_seed()
    counts_after_first = table_counts(db_session)

    second = run_seed()

    assert table_counts(db_session) == counts_after_first
    assert not second.user_created
    assert (second.skills_created, second.jobs_created, second.jobs_duplicates) == (0, 0, 0)
    assert second.jobs_updated == first.jobs_created
    assert second.applications_created == 0
    assert second.applications_skipped == first.applications_created


def test_reseed_keeps_user_edited_profile_and_email(
    db_session: Session, fixed_clock: FixedClock, run_seed: Callable[..., SeedSummary]
) -> None:
    run_seed()
    user = demo_user(db_session)
    edited = ProfileUpdate(
        name="Edited Name", email="edited@example.com", technical_skills=["Rust"], target_roles=[]
    )
    ProfileService(db_session, fixed_clock).update(user, edited)

    run_seed()

    user = demo_user(db_session)
    skills = [skill.name for skill in UserRepository(db_session).list_skills(user.id)]
    assert count(db_session, User) == 1
    assert (user.name, user.email, user.target_roles, skills) == (
        "Edited Name",
        "edited@example.com",
        [],
        ["Rust"],
    )


def test_reseed_keeps_application_changes_and_deletions(
    db_session: Session, fixed_clock: FixedClock, run_seed: Callable[..., SeedSummary]
) -> None:
    run_seed()
    user = demo_user(db_session)
    service = ApplicationService(db_session, fixed_clock)
    saved = application_for(db_session, "seed-002")
    deleted = application_for(db_session, "seed-028")
    service.update(user, saved.id, ApplicationUpdate(status=ApplicationStatus.INTERESTED))
    service.delete(user, deleted.id)
    remaining = count(db_session, Application)

    run_seed()

    assert application_for(db_session, "seed-002").status == "Interested"
    assert count(db_session, Application) == remaining
    job_id = seed_job(db_session, "seed-028").id
    assert db_session.scalar(sa.select(Application).where(Application.job_id == job_id)) is None


def test_seed_resolves_relative_dates_against_clock(
    db_session: Session, fixed_clock: FixedClock, run_seed: Callable[..., SeedSummary]
) -> None:
    run_seed()
    today = fixed_clock.today()

    deadlines = list(db_session.scalars(sa.select(Job.deadline)))
    window_end = today + timedelta(days=14)
    upcoming = [day for day in deadlines if day is not None and today <= day <= window_end]
    interview = application_for(db_session, "seed-001")
    assessment = application_for(db_session, "seed-004")
    assert len(upcoming) >= 5
    assert None in deadlines
    assert seed_job(db_session, "seed-001").deadline == today + timedelta(days=5)
    assert interview.applied_at == today - timedelta(days=12)
    assert interview.interview_date is not None
    assert interview.interview_date.date() == today + timedelta(days=3)
    assert interview.interview_date > fixed_clock.now()
    assert assessment.deadline == today + timedelta(days=2)
    assert application_for(db_session, "seed-002").applied_at is None


def test_reseed_on_later_day_moves_job_deadlines(
    db_session: Session, fixed_clock: FixedClock, run_seed: Callable[..., SeedSummary]
) -> None:
    run_seed()
    later = FixedClock(fixed_clock.now() + timedelta(days=10))

    run_seed(clock=later)

    db_session.expire_all()
    assert seed_job(db_session, "seed-001").deadline == later.today() + timedelta(days=5)


def test_seed_fails_when_demo_email_belongs_to_another_user(
    db_session: Session, make_user: Callable[..., User], run_seed: Callable[..., SeedSummary]
) -> None:
    make_user(DEMO_EMAIL)
    db_session.commit()

    with pytest.raises(EmailTakenError):
        run_seed()

    assert (count(db_session, User), count(db_session, Job)) == (1, 0)


def test_seed_with_invalid_jobs_file_writes_nothing(
    tmp_path: Path, db_session: Session, settings: Settings, run_seed: Callable[..., SeedSummary]
) -> None:
    for name in ("seed_profile.json", "seed_applications.json"):
        shutil.copy(DEFAULT_DATA_DIR / name, tmp_path / name)
    (tmp_path / "seed_jobs.json").write_text(json.dumps({"jobs": []}), encoding="utf-8")

    with pytest.raises(SeedDataError, match="seed_jobs.json"):
        run_seed(config=settings.model_copy(update={"data_dir": tmp_path}))

    assert table_counts(db_session) == (0, 0, 0, 0)


def test_fixture_ingest_after_seed_updates_seed_rows_and_adds_samples(
    db_session: Session,
    fixed_clock: FixedClock,
    settings: Settings,
    run_seed: Callable[..., SeedSummary],
) -> None:
    summary = run_seed()
    service = IngestionService(db_session, fixed_clock, default_sources(settings))

    result = service.ingest(demo_user(db_session), IngestRequest(source="fixture", limit=500))

    assert (result.updated, result.duplicates, result.rejected) == (summary.jobs_created, 0, 0)
    assert result.created == 3
    assert count(db_session, Job) == summary.jobs_created + 3


def test_seed_with_malformed_profile_json_raises_naming_file(
    tmp_path: Path, db_session: Session, settings: Settings, run_seed: Callable[..., SeedSummary]
) -> None:
    for name in ("seed_jobs.json", "seed_applications.json"):
        shutil.copy(DEFAULT_DATA_DIR / name, tmp_path / name)
    (tmp_path / "seed_profile.json").write_text("{not json", encoding="utf-8")

    with pytest.raises(SeedDataError, match="seed_profile.json: invalid JSON"):
        run_seed(config=settings.model_copy(update={"data_dir": tmp_path}))

    assert table_counts(db_session) == (0, 0, 0, 0)


def test_seed_with_invalid_applications_file_raises_naming_file(
    tmp_path: Path, db_session: Session, settings: Settings, run_seed: Callable[..., SeedSummary]
) -> None:
    for name in ("seed_profile.json", "seed_jobs.json"):
        shutil.copy(DEFAULT_DATA_DIR / name, tmp_path / name)
    (tmp_path / "seed_applications.json").write_text(
        json.dumps({"applications": [{"status": "Dreaming"}]}), encoding="utf-8"
    )

    with pytest.raises(SeedDataError, match="seed_applications.json"):
        run_seed(config=settings.model_copy(update={"data_dir": tmp_path}))

    assert table_counts(db_session) == (0, 0, 0, 0)
