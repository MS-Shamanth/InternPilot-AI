"""Application status property P6 (design.md §6, §17): pure machine + service on SQLite."""

from datetime import UTC, datetime

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.stateful import (
    Bundle,
    RuleBasedStateMachine,
    invariant,
    rule,
    run_state_machine_as_test,
)
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.clock import FixedClock
from app.core.database import create_db_engine
from app.core.errors import InvalidStatusTransitionError
from app.models import Application, Base, Job, User
from app.schemas.application import ApplicationCreate, ApplicationUpdate
from app.services.application_service import ApplicationService
from app.services.application_status import ApplicationStatus, is_allowed, transition

pytestmark = pytest.mark.property

SQLITE_MEMORY_URL = "sqlite+pysqlite:///:memory:"
FIXED_NOW = datetime(2025, 1, 15, 9, 30, tzinfo=UTC)
STATUS_VALUES = frozenset(status.value for status in ApplicationStatus)
JOB_COUNT = 3

statuses = st.sampled_from(ApplicationStatus)
targets = st.one_of(st.sampled_from(sorted(STATUS_VALUES)), st.text(max_size=12))


@given(statuses, st.lists(targets, max_size=30))
def test_p6_application_always_has_one_valid_status(
    start: ApplicationStatus, steps: list[str]
) -> None:
    """P6 — R5.2, R5.4, R5.5: after any sequence of moves the status is one valid member.

    Invalid moves raise and leave the status unchanged; non-members are rejected by the schema.

    **Validates: Requirements 5.2, 5.4, 5.5**
    """
    current = start
    for raw in steps:
        if raw not in STATUS_VALUES:
            with pytest.raises(ValidationError):
                ApplicationUpdate.model_validate({"status": raw})
            continue
        target = ApplicationStatus(raw)
        if is_allowed(current, target):
            current = transition(current, target)
            assert current == target
        else:
            with pytest.raises(InvalidStatusTransitionError):
                transition(current, target)
        assert isinstance(current, ApplicationStatus)
        assert current.value in STATUS_VALUES


class ApplicationStatusMachine(RuleBasedStateMachine):
    """Drives `ApplicationService` and checks every stored row against a model of statuses."""

    applications = Bundle("applications")

    def __init__(self) -> None:
        super().__init__()
        self.engine = create_db_engine(SQLITE_MEMORY_URL)
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine, expire_on_commit=True)
        self.service = ApplicationService(self.session, FixedClock(FIXED_NOW))
        self.user = User(name="Demo Student", email="demo@internpilot.dev")
        self.session.add(self.user)
        self.job_ids = [self._add_job(index) for index in range(JOB_COUNT)]
        self.session.commit()
        self.expected: dict[int, ApplicationStatus] = {}
        self.application_by_job: dict[int, int] = {}

    def _add_job(self, index: int) -> int:
        job = Job(
            source="seed",
            external_id=f"ext-{index}",
            dedupe_fingerprint=str(index).rjust(64, "0"),
            title="Frontend Intern",
            company="Example Co",
            location="Remote",
            employment_type="internship",
            work_mode="remote",
            description="Build UI components.",
            application_url=f"https://jobs.example.com/{index}",
            discovered_at=FIXED_NOW,
        )
        self.session.add(job)
        self.session.flush()
        return job.id

    @rule(
        target=applications,
        job_index=st.integers(min_value=0, max_value=JOB_COUNT - 1),
        status=statuses,
    )
    def create(self, job_index: int, status: ApplicationStatus) -> int:
        job_id = self.job_ids[job_index]
        existing = self.application_by_job.get(job_id)
        if existing is not None:
            return existing
        created = self.service.create(self.user, ApplicationCreate(job_id=job_id, status=status))
        self.expected[created.id] = created.status
        self.application_by_job[job_id] = created.id
        return created.id

    @rule(application_id=applications, raw=targets)
    def move(self, application_id: int, raw: str) -> None:
        current = self.expected[application_id]
        if raw not in STATUS_VALUES:
            with pytest.raises(ValidationError):
                ApplicationUpdate.model_validate({"status": raw})
            return
        target = ApplicationStatus(raw)
        update = ApplicationUpdate(status=target)
        if is_allowed(current, target):
            assert self.service.update(self.user, application_id, update).status == target
            self.expected[application_id] = target
        else:
            with pytest.raises(InvalidStatusTransitionError):
                self.service.update(self.user, application_id, update)

    @invariant()
    def stored_status_is_one_valid_member(self) -> None:
        self.session.expire_all()
        for application_id, expected in self.expected.items():
            stored = self.session.get(Application, application_id)
            assert stored is not None
            assert stored.status in STATUS_VALUES
            assert stored.status == expected.value

    def teardown(self) -> None:
        self.session.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()


def test_p6_application_always_has_one_valid_status_in_service() -> None:
    """P6 — R5.2, R5.4, R5.5: the stored row always holds exactly one valid status.

    **Validates: Requirements 5.2, 5.4, 5.5**
    """
    run_state_machine_as_test(
        ApplicationStatusMachine,
        # Each example builds a fresh SQLite schema, so fewer examples keep the suite quick.
        settings=settings(max_examples=50, stateful_step_count=20),
    )
