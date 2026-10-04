"""Model constraints, cascades and portable column types (design.md §4, §4.1, NFR2)."""

from datetime import UTC, date, datetime, timedelta, timezone

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session

from app.models import (
    ActivityEvent,
    Application,
    Base,
    Job,
    JobSkill,
    Skill,
    User,
    UserJobState,
    UserSkill,
)

pytestmark = pytest.mark.integration

DISCOVERED_AT = datetime(2025, 1, 15, 9, 30, tzinfo=UTC)


def make_user(session: Session, email: str = "demo@internpilot.dev") -> User:
    user = User(name="Demo Student", email=email)
    session.add(user)
    session.flush()
    return user


def make_job(session: Session, suffix: str = "1", **overrides: object) -> Job:
    values: dict[str, object] = {
        "source": "seed",
        "external_id": f"ext-{suffix}",
        "dedupe_fingerprint": suffix.rjust(64, "0"),
        "title": "Frontend Intern",
        "company": "Example Co",
        "location": "Remote",
        "employment_type": "internship",
        "work_mode": "remote",
        "description": "Build UI components.",
        "application_url": "https://jobs.example.com/1",
        "discovered_at": DISCOVERED_AT,
    }
    values.update(overrides)
    job = Job(**values)
    session.add(job)
    session.flush()
    return job


def make_skill(session: Session, normalized_name: str = "react") -> Skill:
    skill = Skill(name=normalized_name.title(), normalized_name=normalized_name)
    session.add(skill)
    session.flush()
    return skill


def count(session: Session, model: type[Base]) -> int:
    return session.scalar(sa.select(sa.func.count()).select_from(model)) or 0


# --- metadata -------------------------------------------------------------------------------


def test_metadata_registers_all_tables() -> None:
    assert set(Base.metadata.tables) == {
        "users",
        "skills",
        "user_skills",
        "jobs",
        "job_skills",
        "user_job_states",
        "applications",
        "activity_events",
    }


def test_metadata_constraint_names_are_stable() -> None:
    tables = Base.metadata.tables
    names = {
        constraint.name
        for table in tables.values()
        for constraint in table.constraints
        if constraint.name is not None
    }
    assert {
        "ck_applications_status",
        "uq_applications_user_job",
        "uq_jobs_source_external_id",
        "uq_jobs_dedupe_fingerprint",
        "uq_skills_normalized_name",
        "uq_users_email",
        "uq_users_seed_key",
        "ck_jobs_salary_range",
    } <= names
    index_names = {index.name for table in tables.values() for index in table.indexes}
    assert index_names == {
        "ix_jobs_discovered_at",
        "ix_jobs_deadline",
        "ix_jobs_employment_type",
        "ix_jobs_work_mode",
        "ix_applications_user_status",
        "ix_activity_user_created",
    }


# --- UTCDateTime ----------------------------------------------------------------------------


def test_utc_datetime_aware_utc_round_trips_as_aware_utc(db_session: Session) -> None:
    job_id = make_job(db_session).id
    db_session.commit()

    loaded = db_session.get(Job, job_id)

    assert loaded is not None
    assert loaded.discovered_at == DISCOVERED_AT
    assert loaded.discovered_at.utcoffset() == timedelta(0)


def test_utc_datetime_non_utc_offset_is_converted_to_utc(db_session: Session) -> None:
    ist = timezone(timedelta(hours=5, minutes=30))
    job_id = make_job(db_session, discovered_at=datetime(2025, 1, 15, 15, 0, tzinfo=ist)).id
    db_session.commit()

    loaded = db_session.get(Job, job_id)

    assert loaded is not None
    assert loaded.discovered_at == datetime(2025, 1, 15, 9, 30, tzinfo=UTC)
    assert loaded.discovered_at.tzinfo == UTC


def test_utc_datetime_naive_value_is_rejected(db_session: Session) -> None:
    with pytest.raises(StatementError) as exc_info:
        make_job(db_session, discovered_at=datetime(2025, 1, 15, 9, 30))

    assert isinstance(exc_info.value.orig, ValueError)


def test_utc_datetime_server_default_timestamps_load_as_aware(db_session: Session) -> None:
    user_id = make_user(db_session).id
    db_session.commit()

    loaded = db_session.get(User, user_id)

    assert loaded is not None
    assert loaded.created_at.tzinfo == UTC
    assert loaded.updated_at.tzinfo == UTC


# --- JSON -----------------------------------------------------------------------------------


def test_json_columns_round_trip_nested_values(db_session: Session) -> None:
    projects = [
        {"name": "Tracker", "description": "Kanban", "technologies": ["React"], "url": None}
    ]
    user = make_user(db_session)
    user.projects = projects
    user.target_roles = ["Frontend Intern"]
    db_session.commit()
    user_id = user.id
    db_session.expunge_all()

    loaded = db_session.get(User, user_id)

    assert loaded is not None
    assert loaded.projects == projects
    assert loaded.target_roles == ["Frontend Intern"]
    assert loaded.certifications == []
    assert loaded.resume_text == ""


# --- check constraints ----------------------------------------------------------------------


def test_application_invalid_status_is_rejected(db_session: Session) -> None:
    user, job = make_user(db_session), make_job(db_session)
    db_session.add(Application(user_id=user.id, job_id=job.id, status="saved"))

    with pytest.raises(IntegrityError, match="ck_applications_status"):
        db_session.flush()


def test_application_every_canonical_status_is_accepted(db_session: Session) -> None:
    user = make_user(db_session)
    statuses = [
        "Saved",
        "Interested",
        "Applied",
        "Assessment",
        "Interview",
        "Rejected",
        "Offer",
        "Withdrawn",
    ]
    for index, status in enumerate(statuses):
        job = make_job(db_session, suffix=str(index))
        db_session.add(Application(user_id=user.id, job_id=job.id, status=status))
    db_session.flush()

    assert count(db_session, Application) == len(statuses)


def test_job_salary_min_greater_than_max_is_rejected(db_session: Session) -> None:
    with pytest.raises(IntegrityError, match="ck_jobs_salary_range"):
        make_job(db_session, salary_min=5000, salary_max=1000)


def test_job_salary_min_equal_to_max_is_accepted(db_session: Session) -> None:
    job = make_job(db_session, salary_min=1000, salary_max=1000)

    assert job.id is not None


def test_job_negative_salary_is_rejected(db_session: Session) -> None:
    with pytest.raises(IntegrityError, match="ck_jobs_salary_min_non_negative"):
        make_job(db_session, salary_min=-1)


def test_job_invalid_work_mode_is_rejected(db_session: Session) -> None:
    with pytest.raises(IntegrityError, match="ck_jobs_work_mode"):
        make_job(db_session, work_mode="anywhere")


def test_user_invalid_experience_level_is_rejected(db_session: Session) -> None:
    db_session.add(User(name="A", email="a@example.com", experience_level="expert"))

    with pytest.raises(IntegrityError, match="ck_users_experience_level"):
        db_session.flush()


# --- unique constraints ---------------------------------------------------------------------


def test_application_duplicate_user_job_is_rejected(db_session: Session) -> None:
    user, job = make_user(db_session), make_job(db_session)
    db_session.add(Application(user_id=user.id, job_id=job.id, status="Saved"))
    db_session.flush()
    db_session.add(Application(user_id=user.id, job_id=job.id, status="Applied"))

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_job_duplicate_source_external_id_is_rejected(db_session: Session) -> None:
    make_job(db_session, suffix="1", external_id="same")

    with pytest.raises(IntegrityError):
        make_job(db_session, suffix="2", external_id="same")


def test_job_same_external_id_different_source_is_accepted(db_session: Session) -> None:
    make_job(db_session, suffix="1", external_id="same", source="remotive")
    make_job(db_session, suffix="2", external_id="same", source="arbeitnow")

    assert count(db_session, Job) == 2


def test_job_duplicate_fingerprint_is_rejected(db_session: Session) -> None:
    make_job(db_session, suffix="1", dedupe_fingerprint="f" * 64)

    with pytest.raises(IntegrityError):
        make_job(db_session, suffix="2", dedupe_fingerprint="f" * 64)


def test_skill_duplicate_normalized_name_is_rejected(db_session: Session) -> None:
    make_skill(db_session, "react")

    with pytest.raises(IntegrityError):
        make_skill(db_session, "react")


def test_user_duplicate_email_is_rejected(db_session: Session) -> None:
    make_user(db_session, "demo@internpilot.dev")

    with pytest.raises(IntegrityError):
        make_user(db_session, "demo@internpilot.dev")


def test_user_duplicate_seed_key_is_rejected_but_nulls_allowed(db_session: Session) -> None:
    db_session.add_all(
        [
            User(name="A", email="a@example.com", seed_key="demo"),
            User(name="B", email="b@example.com"),
            User(name="C", email="c@example.com"),
        ]
    )
    db_session.flush()
    db_session.add(User(name="D", email="d@example.com", seed_key="demo"))

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_user_skill_duplicate_pair_is_rejected(db_session: Session) -> None:
    user, skill = make_user(db_session), make_skill(db_session)
    db_session.add(UserSkill(user_id=user.id, skill_id=skill.id))
    db_session.flush()
    db_session.expunge_all()
    db_session.add(UserSkill(user_id=user.id, skill_id=skill.id))

    with pytest.raises(IntegrityError):
        db_session.flush()


# --- cascades -------------------------------------------------------------------------------


def test_deleting_user_cascades_to_owned_rows(db_session: Session) -> None:
    user, job, skill = make_user(db_session), make_job(db_session), make_skill(db_session)
    db_session.add_all(
        [
            UserSkill(user_id=user.id, skill_id=skill.id),
            UserJobState(user_id=user.id, job_id=job.id, is_bookmarked=True),
            Application(user_id=user.id, job_id=job.id, status="Saved"),
            ActivityEvent(user_id=user.id, type="job_bookmarked", job_id=job.id, message="m"),
        ]
    )
    db_session.commit()

    db_session.execute(sa.delete(User).where(User.id == user.id))
    db_session.commit()

    assert count(db_session, Application) == 0
    assert count(db_session, UserSkill) == 0
    assert count(db_session, UserJobState) == 0
    assert count(db_session, ActivityEvent) == 0
    assert count(db_session, Job) == 1
    assert count(db_session, Skill) == 1


def test_deleting_job_cascades_and_nulls_activity_job(db_session: Session) -> None:
    user, job, skill = make_user(db_session), make_job(db_session), make_skill(db_session)
    db_session.add_all(
        [
            JobSkill(job_id=job.id, skill_id=skill.id, is_required=True),
            UserJobState(user_id=user.id, job_id=job.id, is_hidden=True),
            Application(user_id=user.id, job_id=job.id, status="Applied"),
            ActivityEvent(user_id=user.id, type="status_changed", job_id=job.id, message="m"),
        ]
    )
    db_session.commit()

    db_session.execute(sa.delete(Job).where(Job.id == job.id))
    db_session.commit()

    assert count(db_session, JobSkill) == 0
    assert count(db_session, UserJobState) == 0
    assert count(db_session, Application) == 0
    event_job_ids = db_session.scalars(sa.select(ActivityEvent.job_id)).all()
    assert event_job_ids == [None]
    assert count(db_session, Skill) == 1


def test_application_foreign_key_to_missing_job_is_rejected(db_session: Session) -> None:
    user = make_user(db_session)
    db_session.add(Application(user_id=user.id, job_id=9999, status="Saved"))

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_job_skill_relationship_loads_skill(db_session: Session) -> None:
    job, skill = make_job(db_session), make_skill(db_session, "postgresql")
    job.job_skills.append(JobSkill(skill_id=skill.id, is_required=False))
    job_id = job.id
    db_session.commit()
    db_session.expunge_all()

    loaded = db_session.get(Job, job_id)

    assert loaded is not None
    assert [(link.skill.normalized_name, link.is_required) for link in loaded.job_skills] == [
        ("postgresql", False)
    ]


def test_application_dates_round_trip(db_session: Session) -> None:
    user, job = make_user(db_session), make_job(db_session)
    interview = datetime(2025, 2, 1, 14, 0, tzinfo=UTC)
    application = Application(
        user_id=user.id,
        job_id=job.id,
        status="Interview",
        applied_at=date(2025, 1, 20),
        interview_date=interview,
    )
    db_session.add(application)
    db_session.flush()
    application_id = application.id
    db_session.commit()
    db_session.expunge_all()

    loaded = db_session.get(Application, application_id)

    assert loaded is not None
    assert loaded.applied_at == date(2025, 1, 20)
    assert loaded.interview_date == interview
    assert loaded.notes == ""
