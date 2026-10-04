"""Application tracker use cases (R5, R2.10-R2.11, design.md §6).

Every mutating method is one unit of work: the change and its activity event are committed
together, and any failure rolls the whole thing back (R5.12).
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.errors import DuplicateApplicationError, NotFoundError
from app.models import Application as ApplicationRecord
from app.models import Job, User
from app.repositories.activity_repository import ActivityRepository
from app.repositories.application_repository import (
    APPLICATION_LIST_LIMIT,
    ApplicationRepository,
)
from app.repositories.job_repository import JobRepository
from app.schemas.application import (
    EDITABLE_FIELDS,
    Application,
    ApplicationCreate,
    ApplicationsMeta,
    ApplicationUpdate,
)
from app.services.application_status import (
    CANONICAL_ORDER,
    SUBMITTED_STATUSES,
    ApplicationStatus,
    allowed_targets,
    transition,
)

logger = logging.getLogger(__name__)

APPLICATION_CREATED_EVENT = "application_created"
STATUS_CHANGED_EVENT = "status_changed"
APPLICATION_UPDATED_EVENT = "application_updated"
APPLICATION_DELETED_EVENT = "application_deleted"
ACTIVITY_MESSAGE_MAX_LENGTH = 300

JOB_NOT_FOUND_MESSAGE = "Job not found."
APPLICATION_NOT_FOUND_MESSAGE = "Application not found."


@dataclass(frozen=True)
class MarkAppliedResult:
    """Outcome of "mark as applied": `created` tells the route to answer 201 instead of 200."""

    application: Application
    created: bool


def job_label(job: Job) -> str:
    return f"{job.title} at {job.company}"


def activity_message(text: str) -> str:
    """Fit a message into `activity_events.message` (varchar 300)."""
    if len(text) <= ACTIVITY_MESSAGE_MAX_LENGTH:
        return text
    return text[: ACTIVITY_MESSAGE_MAX_LENGTH - 1] + "…"


def _resolve_applied_at(
    status: ApplicationStatus, applied_at: date | None, today: date
) -> date | None:
    """R5.6: entering a submitted status with no application date records today."""
    if status in SUBMITTED_STATUSES and applied_at is None:
        return today
    return applied_at


class ApplicationService:
    """Create, list, update and delete the current user's applications."""

    def __init__(self, session: Session, clock: Clock) -> None:
        self._session = session
        self._clock = clock
        self._applications = ApplicationRepository(session)
        self._jobs = JobRepository(session)
        self._activity = ActivityRepository(session)

    def create(self, user: User, data: ApplicationCreate) -> Application:
        """Create an application (R5.1, R5.3, R5.6).

        Raises `NotFoundError` for an unknown job and `DuplicateApplicationError` when the user
        already tracks the job.
        """
        try:
            job = self._require_job(data.job_id)
            if self._applications.get_by_job(user.id, job.id) is not None:
                raise DuplicateApplicationError
            record = self.insert(user, job, data)
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        logger.info("Application %d created for user_id=%d", record.id, user.id)
        return self._to_schema(record)

    def list_applications(
        self, user: User, statuses: list[ApplicationStatus] | None = None
    ) -> list[Application]:
        """The user's applications with job summaries, optionally by status (R5.9).

        Unpaginated by design and capped at 500 (design.md §8 pagination exception).
        """
        values = None if statuses is None else [status.value for status in statuses]
        records = self._applications.list_for_user(user.id, statuses=values)
        if len(records) >= APPLICATION_LIST_LIMIT:
            logger.warning(
                "Application list for user_id=%d reached the cap of %d",
                user.id,
                APPLICATION_LIST_LIMIT,
            )
        return [self._to_schema(record) for record in records]

    def update(self, user: User, application_id: int, data: ApplicationUpdate) -> Application:
        """Apply the fields present in `data` (R5.4-R5.7).

        A status change goes through `transition()`; a disallowed move raises
        `InvalidStatusTransitionError` and nothing is changed. A request that changes nothing
        is a no-op success: no write, no event, `updated_at` untouched.
        """
        try:
            record = self._require_application(user, application_id)
            previous_status = ApplicationStatus(record.status)
            target = previous_status
            if "status" in data.model_fields_set and data.status is not None:
                target = transition(previous_status, data.status)
            changed_fields = self._apply_fields(record, data)
            status_changed = target != previous_status
            if status_changed:
                record.status = target.value
                record.applied_at = _resolve_applied_at(
                    target, record.applied_at, self._clock.today()
                )
            if not status_changed and not changed_fields:
                return self._to_schema(record)
            now = self._clock.now()
            record.updated_at = now
            self._record_update_event(user, record, previous_status, status_changed, now)
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        logger.info("Application %d updated for user_id=%d", application_id, user.id)
        return self._to_schema(record)

    def delete(self, user: User, application_id: int) -> None:
        """Remove the application (R5.8); another user's application is `NotFoundError`."""
        try:
            record = self._require_application(user, application_id)
            job_id, label = record.job_id, job_label(record.job)
            self._applications.delete(record)
            self._activity.add(
                user.id,
                APPLICATION_DELETED_EVENT,
                activity_message(f"Deleted application for {label}"),
                job_id=job_id,
                application_id=application_id,
                created_at=self._clock.now(),
            )
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        logger.info("Application %d deleted for user_id=%d", application_id, user.id)

    def mark_applied(self, user: User, job_id: int) -> MarkAppliedResult:
        """Mark the job as applied (R2.10, R2.11).

        No application: create one in `Applied` (`created=True`). `Saved`/`Interested`: move
        to `Applied`. Already `Applied`: returned unchanged with no event. Any other status:
        `InvalidStatusTransitionError` from `transition()`.
        """
        try:
            job = self._require_job(job_id)
            record = self._applications.get_by_job(user.id, job.id)
            if record is None:
                data = ApplicationCreate(job_id=job.id, status=ApplicationStatus.APPLIED)
                record = self.insert(user, job, data)
                self._session.commit()
                logger.info("Application %d created via apply for user_id=%d", record.id, user.id)
                return MarkAppliedResult(self._to_schema(record), created=True)
            previous_status = ApplicationStatus(record.status)
            target = transition(previous_status, ApplicationStatus.APPLIED)
            if target == previous_status:
                return MarkAppliedResult(self._to_schema(record), created=False)
            now = self._clock.now()
            record.status = target.value
            record.applied_at = _resolve_applied_at(target, record.applied_at, self._clock.today())
            record.updated_at = now
            self._record_update_event(user, record, previous_status, True, now)
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        logger.info("Application %d marked applied for user_id=%d", record.id, user.id)
        return MarkAppliedResult(self._to_schema(record), created=False)

    def meta(self) -> ApplicationsMeta:
        """Statuses and allowed transitions in canonical order (R5.10)."""
        return ApplicationsMeta(
            statuses=list(CANONICAL_ORDER),
            transitions={status: list(allowed_targets(status)) for status in CANONICAL_ORDER},
        )

    def _require_job(self, job_id: int) -> Job:
        job = self._jobs.get_by_id(job_id)
        if job is None:
            raise NotFoundError(JOB_NOT_FOUND_MESSAGE)
        return job

    def _require_application(self, user: User, application_id: int) -> ApplicationRecord:
        record = self._applications.get(user.id, application_id)
        if record is None:
            raise NotFoundError(APPLICATION_NOT_FOUND_MESSAGE)
        return record

    def insert(self, user: User, job: Job, data: ApplicationCreate) -> ApplicationRecord:
        """Stage a new application and its `application_created` event without committing.

        The caller owns the unit of work and has already checked that (user, job) has no
        application; `create`, `mark_applied` and the seed (`SeedService`) use it.
        """
        now = self._clock.now()
        record = self._applications.add(
            ApplicationRecord(
                user_id=user.id,
                job_id=job.id,
                status=data.status.value,
                notes=data.notes,
                applied_at=_resolve_applied_at(data.status, data.applied_at, self._clock.today()),
                deadline=data.deadline,
                interview_date=data.interview_date,
                recruiter_name=data.recruiter_name,
                recruiter_email=data.recruiter_email,
                outcome=data.outcome,
                created_at=now,
                updated_at=now,
            )
        )
        self._activity.add(
            user.id,
            APPLICATION_CREATED_EVENT,
            activity_message(f"Added {job_label(job)} as {data.status.value}"),
            job_id=job.id,
            application_id=record.id,
            created_at=now,
        )
        return record

    @staticmethod
    def _apply_fields(record: ApplicationRecord, data: ApplicationUpdate) -> list[str]:
        """Copy the editable fields present in `data`; return the names whose value changed."""
        changed: list[str] = []
        for name in EDITABLE_FIELDS:
            if name not in data.model_fields_set:
                continue
            value = getattr(data, name)
            if getattr(record, name) != value:
                setattr(record, name, value)
                changed.append(name)
        return changed

    def _record_update_event(
        self,
        user: User,
        record: ApplicationRecord,
        previous_status: ApplicationStatus,
        status_changed: bool,
        now: datetime,
    ) -> None:
        label = job_label(record.job)
        if status_changed:
            event_type = STATUS_CHANGED_EVENT
            message = f"Moved {label} from {previous_status.value} to {record.status}"
        else:
            event_type = APPLICATION_UPDATED_EVENT
            message = f"Updated application for {label}"
        self._activity.add(
            user.id,
            event_type,
            activity_message(message),
            job_id=record.job_id,
            application_id=record.id,
            created_at=now,
        )

    @staticmethod
    def _to_schema(record: ApplicationRecord) -> Application:
        return Application.model_validate(record)
