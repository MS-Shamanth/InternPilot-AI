"""ApplicationService against a real session (R5.1-R5.10, R5.12, R2.10-R2.11, design.md §6)."""

from collections.abc import Callable
from datetime import UTC, date, datetime

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.clock import FixedClock
from app.core.errors import (
    DuplicateApplicationError,
    InvalidStatusTransitionError,
    NotFoundError,
)
from app.models import ActivityEvent, Application, Job, User
from app.schemas.application import ApplicationCreate, ApplicationUpdate
from app.services.application_service import ApplicationService
from app.services.application_status import ApplicationStatus

pytestmark = pytest.mark.integration

FIXED_TODAY = date(2025, 1, 15)
FIXED_NOW = datetime(2025, 1, 15, 9, 30, tzinfo=UTC)
EARLIER = datetime(2025, 1, 1, 8, 0, tzinfo=UTC)


@pytest.fixture
def service(db_session: Session, fixed_clock: FixedClock) -> ApplicationService:
    return ApplicationService(db_session, fixed_clock)


@pytest.fixture
def user(db_session: Session, make_user: Callable[..., User]) -> User:
    created = make_user()
    db_session.commit()
    return created


@pytest.fixture
def job(db_session: Session, make_job: Callable[..., Job]) -> Job:
    created = make_job()
    db_session.commit()
    return created


@pytest.fixture
def add_application(db_session: Session) -> Callable[..., Application]:
    """Insert a committed application directly, bypassing the service (and its events)."""

    def factory(user: User, job: Job, status: str = "Saved", **overrides: object) -> Application:
        values: dict[str, object] = {"created_at": EARLIER, "updated_at": EARLIER}
        values.update(overrides)
        application = Application(user_id=user.id, job_id=job.id, status=status, **values)
        db_session.add(application)
        db_session.commit()
        return application

    return factory


def events(session: Session) -> list[tuple[str, int | None, int | None]]:
    rows = session.scalars(sa.select(ActivityEvent).order_by(ActivityEvent.id))
    return [(event.type, event.job_id, event.application_id) for event in rows]


def stored_status(session: Session, application_id: int) -> str | None:
    session.expire_all()
    return session.scalar(sa.select(Application.status).where(Application.id == application_id))


def test_create_without_status_defaults_to_saved(
    service: ApplicationService, user: User, job: Job
) -> None:
    created = service.create(user, ApplicationCreate(job_id=job.id))

    assert created.status is ApplicationStatus.SAVED
    assert created.applied_at is None
    assert created.notes == ""
    assert created.created_at == FIXED_NOW
    assert created.updated_at == FIXED_NOW
    assert created.job.title == "Frontend Intern"


def test_create_submitted_status_sets_applied_at_to_today(
    service: ApplicationService, user: User, job: Job
) -> None:
    created = service.create(user, ApplicationCreate(job_id=job.id, status="Interview"))

    assert created.applied_at == FIXED_TODAY


def test_create_with_applied_at_keeps_given_date(
    service: ApplicationService, user: User, job: Job
) -> None:
    data = ApplicationCreate(job_id=job.id, status="Applied", applied_at=date(2024, 12, 20))

    assert service.create(user, data).applied_at == date(2024, 12, 20)


def test_create_unknown_job_raises_not_found(
    service: ApplicationService, user: User, db_session: Session
) -> None:
    with pytest.raises(NotFoundError):
        service.create(user, ApplicationCreate(job_id=999))

    assert events(db_session) == []


def test_create_duplicate_raises_and_keeps_one_record(
    service: ApplicationService, user: User, job: Job, db_session: Session
) -> None:
    service.create(user, ApplicationCreate(job_id=job.id))

    with pytest.raises(DuplicateApplicationError):
        service.create(user, ApplicationCreate(job_id=job.id, status="Applied"))

    assert db_session.scalar(sa.select(sa.func.count()).select_from(Application)) == 1


def test_create_records_application_created_event(
    service: ApplicationService, user: User, job: Job, db_session: Session
) -> None:
    created = service.create(user, ApplicationCreate(job_id=job.id))

    assert events(db_session) == [("application_created", job.id, created.id)]
    event = db_session.scalars(sa.select(ActivityEvent)).one()
    assert event.created_at == FIXED_NOW
    assert event.message == "Added Frontend Intern at Example Co as Saved"


def test_list_status_filter_returns_only_matching(
    service: ApplicationService,
    user: User,
    make_job: Callable[..., Job],
    add_application: Callable[..., Application],
) -> None:
    applied = add_application(user, make_job("2"), "Applied")
    add_application(user, make_job("3"), "Saved")

    result = service.list_applications(user, [ApplicationStatus.APPLIED])

    assert [application.id for application in result] == [applied.id]
    assert len(service.list_applications(user)) == 2


def test_update_allowed_transition_changes_status_and_records_event(
    service: ApplicationService,
    user: User,
    job: Job,
    add_application: Callable[..., Application],
    db_session: Session,
) -> None:
    application = add_application(user, job, "Saved")

    updated = service.update(user, application.id, ApplicationUpdate(status="Interested"))

    assert updated.status is ApplicationStatus.INTERESTED
    assert updated.updated_at == FIXED_NOW
    assert events(db_session) == [("status_changed", job.id, application.id)]


def test_update_disallowed_transition_raises_and_leaves_status(
    service: ApplicationService,
    user: User,
    job: Job,
    add_application: Callable[..., Application],
    db_session: Session,
) -> None:
    application = add_application(user, job, "Offer")

    with pytest.raises(InvalidStatusTransitionError) as exc_info:
        service.update(user, application.id, ApplicationUpdate(status="Applied", notes="x"))

    assert exc_info.value.details == {"from": "Offer", "to": "Applied", "allowed": ["Withdrawn"]}
    assert stored_status(db_session, application.id) == "Offer"
    assert db_session.scalar(sa.select(Application.notes)) == ""
    assert events(db_session) == []


def test_update_same_status_is_noop_success(
    service: ApplicationService,
    user: User,
    job: Job,
    add_application: Callable[..., Application],
    db_session: Session,
) -> None:
    application = add_application(user, job, "Interview", applied_at=date(2025, 1, 2))

    updated = service.update(user, application.id, ApplicationUpdate(status="Interview"))

    assert updated.status is ApplicationStatus.INTERVIEW
    assert updated.updated_at == EARLIER
    assert events(db_session) == []


def test_update_move_to_applied_sets_applied_at_today(
    service: ApplicationService,
    user: User,
    job: Job,
    add_application: Callable[..., Application],
) -> None:
    application = add_application(user, job, "Saved")

    updated = service.update(user, application.id, ApplicationUpdate(status="Applied"))

    assert updated.applied_at == FIXED_TODAY


def test_update_move_to_submitted_keeps_existing_applied_at(
    service: ApplicationService,
    user: User,
    job: Job,
    add_application: Callable[..., Application],
) -> None:
    application = add_application(user, job, "Applied", applied_at=date(2025, 1, 3))

    updated = service.update(user, application.id, ApplicationUpdate(status="Assessment"))

    assert updated.applied_at == date(2025, 1, 3)


def test_update_fields_persists_and_records_updated_event(
    service: ApplicationService,
    user: User,
    job: Job,
    add_application: Callable[..., Application],
    db_session: Session,
) -> None:
    application = add_application(user, job, "Applied", recruiter_name="Sam")
    interview = datetime(2025, 1, 20, 14, 0, tzinfo=UTC)
    data = ApplicationUpdate.model_validate(
        {"notes": "Call went well", "interview_date": interview, "recruiter_name": None}
    )

    updated = service.update(user, application.id, data)

    assert updated.notes == "Call went well"
    assert updated.interview_date == interview
    assert updated.recruiter_name is None
    assert updated.status is ApplicationStatus.APPLIED
    assert updated.updated_at == FIXED_NOW
    assert events(db_session) == [("application_updated", job.id, application.id)]


def test_update_omitted_fields_are_untouched(
    service: ApplicationService,
    user: User,
    job: Job,
    add_application: Callable[..., Application],
) -> None:
    application = add_application(user, job, "Saved", recruiter_name="Sam", outcome="Pending")

    updated = service.update(user, application.id, ApplicationUpdate(notes="Follow up"))

    assert updated.recruiter_name == "Sam"
    assert updated.outcome == "Pending"


def test_update_other_users_application_raises_not_found(
    service: ApplicationService,
    user: User,
    job: Job,
    make_user: Callable[..., User],
    add_application: Callable[..., Application],
) -> None:
    other = make_user(email="other@example.com")
    application = add_application(other, job, "Saved")

    with pytest.raises(NotFoundError):
        service.update(user, application.id, ApplicationUpdate(notes="x"))


def test_delete_removes_and_records_event(
    service: ApplicationService,
    user: User,
    job: Job,
    add_application: Callable[..., Application],
    db_session: Session,
) -> None:
    application = add_application(user, job, "Saved")
    application_id = application.id

    service.delete(user, application_id)

    assert db_session.get(Application, application_id) is None
    assert events(db_session) == [("application_deleted", job.id, application_id)]


def test_delete_other_users_application_raises_not_found(
    service: ApplicationService,
    user: User,
    job: Job,
    make_user: Callable[..., User],
    add_application: Callable[..., Application],
    db_session: Session,
) -> None:
    other = make_user(email="other@example.com")
    application = add_application(other, job, "Saved")

    with pytest.raises(NotFoundError):
        service.delete(user, application.id)

    assert stored_status(db_session, application.id) == "Saved"


def test_mark_applied_without_application_creates_applied(
    service: ApplicationService, user: User, job: Job, db_session: Session
) -> None:
    result = service.mark_applied(user, job.id)

    assert result.created is True
    assert result.application.status is ApplicationStatus.APPLIED
    assert result.application.applied_at == FIXED_TODAY
    assert events(db_session) == [("application_created", job.id, result.application.id)]


@pytest.mark.parametrize("status", ["Saved", "Interested"])
def test_mark_applied_from_saved_or_interested_transitions(
    service: ApplicationService,
    user: User,
    job: Job,
    add_application: Callable[..., Application],
    db_session: Session,
    status: str,
) -> None:
    application = add_application(user, job, status)

    result = service.mark_applied(user, job.id)

    assert result.created is False
    assert result.application.id == application.id
    assert result.application.status is ApplicationStatus.APPLIED
    assert result.application.applied_at == FIXED_TODAY
    assert events(db_session) == [("status_changed", job.id, application.id)]


def test_mark_applied_already_applied_returns_unchanged(
    service: ApplicationService,
    user: User,
    job: Job,
    add_application: Callable[..., Application],
    db_session: Session,
) -> None:
    application = add_application(user, job, "Applied", applied_at=date(2025, 1, 2))

    result = service.mark_applied(user, job.id)

    assert result.created is False
    assert result.application.id == application.id
    assert result.application.applied_at == date(2025, 1, 2)
    assert result.application.updated_at == EARLIER
    assert events(db_session) == []


@pytest.mark.parametrize("status", ["Assessment", "Interview", "Rejected", "Offer", "Withdrawn"])
def test_mark_applied_other_status_raises_and_leaves_status(
    service: ApplicationService,
    user: User,
    job: Job,
    add_application: Callable[..., Application],
    db_session: Session,
    status: str,
) -> None:
    application = add_application(user, job, status)

    with pytest.raises(InvalidStatusTransitionError):
        service.mark_applied(user, job.id)

    assert stored_status(db_session, application.id) == status
    assert events(db_session) == []


def test_mark_applied_unknown_job_raises_not_found(service: ApplicationService, user: User) -> None:
    with pytest.raises(NotFoundError):
        service.mark_applied(user, 999)


def test_meta_lists_statuses_and_transitions_in_canonical_order(
    service: ApplicationService,
) -> None:
    meta = service.meta()

    assert [status.value for status in meta.statuses] == [
        "Saved",
        "Interested",
        "Applied",
        "Assessment",
        "Interview",
        "Rejected",
        "Offer",
        "Withdrawn",
    ]
    assert meta.transitions[ApplicationStatus.INTERVIEW] == [
        ApplicationStatus.ASSESSMENT,
        ApplicationStatus.REJECTED,
        ApplicationStatus.OFFER,
        ApplicationStatus.WITHDRAWN,
    ]
