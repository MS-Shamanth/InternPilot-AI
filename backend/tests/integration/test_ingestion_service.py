"""Integration tests for `IngestionService` (R10.4-R10.8, design.md §11.4, §11.5)."""

from collections.abc import Callable
from dataclasses import dataclass, field

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.clock import FixedClock
from app.core.errors import IngestionSourceUnavailableError
from app.models import ActivityEvent, Job, User
from app.repositories.job_repository import JobRepository
from app.schemas.common import JobSource
from app.schemas.ingest import IngestRequest, RawFormat
from app.services.ingestion.normalizers import fingerprint
from app.services.ingestion.service import IngestionService, IngestionSources
from app.services.ingestion.sources import RawBatch, SourceUnavailableError

pytestmark = pytest.mark.integration


@dataclass
class FakeSource:
    """A `JobSource` returning fixed batches or failing with a reason."""

    name: str
    batches: list[RawBatch] = field(default_factory=list)
    failure: str | None = None
    calls: int = 0

    def fetch(self, limit: int) -> list[RawBatch]:
        self.calls += 1
        if self.failure is not None:
            raise SourceUnavailableError(self.failure)
        return self.batches


def job_item(external_id: str, title: str = "Frontend Intern", **overrides: object) -> dict:
    item: dict[str, object] = {
        "external_id": external_id,
        "title": title,
        "company": "Example Co",
        "location": "Remote",
        "employment_type": "internship",
        "work_mode": "remote",
        "description": "<p>Build UI</p>",
        "application_url": f"https://jobs.example.com/{external_id}",
        "required_skills": ["React"],
        "preferred_skills": ["TypeScript"],
    }
    item.update(overrides)
    return item


def batch(source: JobSource, *items: object) -> RawBatch:
    return RawBatch(RawFormat.NORMALIZED, source, list(items))


def make_service(
    session: Session,
    clock: FixedClock,
    remotive: FakeSource | None = None,
    fixture: FakeSource | None = None,
) -> IngestionService:
    sources = IngestionSources(
        remotive=remotive or FakeSource("remotive"),
        arbeitnow=FakeSource("arbeitnow"),
        fixture=fixture or FakeSource("fixture"),
    )
    return IngestionService(session, clock, sources)


def payload_request(*items: object) -> IngestRequest:
    return IngestRequest(source="payload", format="normalized", payload=list(items))


def all_jobs(session: Session) -> list[Job]:
    return list(session.scalars(sa.select(Job).order_by(Job.id)))


@pytest.fixture
def user(make_user: Callable[..., User]) -> User:
    return make_user()


def test_ingest_payload_creates_jobs_with_skills_and_event(
    db_session: Session, fixed_clock: FixedClock, user: User
) -> None:
    result = make_service(db_session, fixed_clock).ingest(
        user, payload_request(job_item("p-1"), job_item("p-2", title="Backend Intern"))
    )

    assert (result.fetched, result.created, result.updated, result.duplicates) == (2, 2, 0, 0)
    assert result.source == result.requested_source == "payload"
    jobs = all_jobs(db_session)
    assert [job.source for job in jobs] == ["payload", "payload"]
    assert jobs[0].description == "Build UI"
    assert jobs[0].discovered_at == fixed_clock.now()
    assert jobs[0].dedupe_fingerprint == fingerprint("Frontend Intern", "Example Co", "Remote")
    stored = JobRepository(db_session).get_by_id(jobs[0].id)
    assert stored is not None
    assert {(link.skill.normalized_name, link.is_required) for link in stored.job_skills} == {
        ("react", True),
        ("typescript", False),
    }
    events = list(db_session.scalars(sa.select(ActivityEvent)))
    assert [event.type for event in events] == ["jobs_ingested"]


def test_ingest_same_source_external_id_updates_existing_job(
    db_session: Session, fixed_clock: FixedClock, user: User
) -> None:
    service = make_service(db_session, fixed_clock)
    service.ingest(user, payload_request(job_item("p-1")))

    result = service.ingest(
        user,
        payload_request(job_item("p-1", title="Frontend Intern (Summer)", required_skills=["Vue"])),
    )

    assert (result.created, result.updated) == (0, 1)
    jobs = all_jobs(db_session)
    assert len(jobs) == 1
    assert jobs[0].title == "Frontend Intern (Summer)"
    stored = JobRepository(db_session).get_by_id(jobs[0].id)
    assert stored is not None
    assert {link.skill.normalized_name for link in stored.job_skills} == {"vue", "typescript"}


def test_ingest_fingerprint_match_from_other_source_counts_duplicate(
    db_session: Session, fixed_clock: FixedClock, user: User
) -> None:
    fixture = FakeSource("fixture", [batch(JobSource.SEED, job_item("seed-001"))])
    service = make_service(db_session, fixed_clock, fixture=fixture)
    service.ingest(user, IngestRequest(source="fixture"))

    result = service.ingest(
        user, payload_request(job_item("p-9", title="frontend-intern", company="EXAMPLE CO"))
    )

    assert (result.created, result.duplicates) == (0, 1)
    assert [job.source for job in all_jobs(db_session)] == ["seed"]


def test_ingest_same_source_new_external_id_same_fingerprint_counts_duplicate(
    db_session: Session, fixed_clock: FixedClock, user: User
) -> None:
    result = make_service(db_session, fixed_clock).ingest(
        user, payload_request(job_item("p-1"), job_item("p-2"))
    )
    assert (result.created, result.duplicates) == (1, 1)


def test_ingest_update_colliding_with_other_job_fingerprint_counts_duplicate(
    db_session: Session, fixed_clock: FixedClock, user: User
) -> None:
    service = make_service(db_session, fixed_clock)
    service.ingest(user, payload_request(job_item("p-1"), job_item("p-2", title="Backend Intern")))

    result = service.ingest(user, payload_request(job_item("p-2", title="Frontend Intern")))

    assert (result.updated, result.duplicates) == (0, 1)
    assert [job.title for job in all_jobs(db_session)] == ["Frontend Intern", "Backend Intern"]


def test_ingest_counts_rejected_items_without_aborting(
    db_session: Session, fixed_clock: FixedClock, user: User
) -> None:
    result = make_service(db_session, fixed_clock).ingest(
        user, payload_request(job_item("p-1"), job_item("p-2", title=""), "junk")
    )

    assert (result.fetched, result.created, result.rejected) == (3, 1, 2)
    assert [error.index for error in result.errors] == [1, 2]
    assert result.errors[0].reason.startswith("title:")


def test_ingest_errors_are_capped_at_fifty(
    db_session: Session, fixed_clock: FixedClock, user: User
) -> None:
    result = make_service(db_session, fixed_clock).ingest(user, payload_request(*["junk"] * 60))
    assert result.rejected == 60
    assert len(result.errors) == 50


def test_ingest_public_failure_falls_back_to_fixture(
    db_session: Session, fixed_clock: FixedClock, user: User
) -> None:
    remotive = FakeSource("remotive", failure="timeout")
    fixture = FakeSource(
        "fixture",
        [
            batch(JobSource.SEED, job_item("seed-001")),
            batch(JobSource.FIXTURE, job_item("fx-1", title="QA Intern")),
        ],
    )

    result = make_service(db_session, fixed_clock, remotive=remotive, fixture=fixture).ingest(
        user, IngestRequest(source="remotive")
    )

    assert result.fallback_used is True
    assert (result.requested_source, result.source) == ("remotive", "fixture")
    assert result.created == 2
    assert result.errors[0].model_dump() == {"index": None, "reason": "remotive: timeout"}
    assert [job.source for job in all_jobs(db_session)] == ["seed", "fixture"]


def test_ingest_fallback_rerun_updates_seed_rows_instead_of_duplicating(
    db_session: Session, fixed_clock: FixedClock, user: User
) -> None:
    fixture = FakeSource("fixture", [batch(JobSource.SEED, job_item("seed-001"))])
    service = make_service(
        db_session, fixed_clock, remotive=FakeSource("remotive", failure="timeout"), fixture=fixture
    )
    service.ingest(user, IngestRequest(source="fixture"))

    result = service.ingest(user, IngestRequest(source="remotive"))

    assert (result.created, result.updated, result.duplicates) == (0, 1, 0)


def test_ingest_failure_without_fallback_raises_and_writes_nothing(
    db_session: Session, fixed_clock: FixedClock, user: User
) -> None:
    fixture = FakeSource("fixture", [batch(JobSource.SEED, job_item("seed-001"))])
    service = make_service(
        db_session,
        fixed_clock,
        remotive=FakeSource("remotive", failure="http_status_500"),
        fixture=fixture,
    )

    with pytest.raises(IngestionSourceUnavailableError) as caught:
        service.ingest(user, IngestRequest(source="remotive", fallback=False))

    assert caught.value.details == {"source": "remotive", "reason": "http_status_500"}
    assert fixture.calls == 0
    assert all_jobs(db_session) == []
    assert db_session.scalar(sa.select(sa.func.count()).select_from(ActivityEvent)) == 0


def test_ingest_fixture_failure_is_not_retried(
    db_session: Session, fixed_clock: FixedClock, user: User
) -> None:
    fixture = FakeSource("fixture", failure="invalid_json")
    service = make_service(db_session, fixed_clock, fixture=fixture)
    with pytest.raises(IngestionSourceUnavailableError):
        service.ingest(user, IngestRequest(source="fixture"))
    assert fixture.calls == 1


def test_ingest_fallback_fixture_failure_raises_and_writes_nothing(
    db_session: Session, fixed_clock: FixedClock, user: User
) -> None:
    service = make_service(
        db_session,
        fixed_clock,
        remotive=FakeSource("remotive", failure="timeout"),
        fixture=FakeSource("fixture", failure="read_error"),
    )

    with pytest.raises(IngestionSourceUnavailableError) as caught:
        service.ingest(user, IngestRequest(source="remotive"))

    assert caught.value.details == {"source": "fixture", "reason": "read_error"}
    assert all_jobs(db_session) == []


def test_ingest_store_failure_rolls_back_every_write(
    db_session: Session, fixed_clock: FixedClock
) -> None:
    """R10.7 single transaction: a failing activity insert (unknown user FK) undoes the jobs."""
    unsaved_user = User(id=999_999, name="Ghost", email="ghost@example.com")

    with pytest.raises(sa.exc.IntegrityError):
        make_service(db_session, fixed_clock).ingest(unsaved_user, payload_request(job_item("p-1")))

    assert all_jobs(db_session) == []
    assert db_session.scalar(sa.select(sa.func.count()).select_from(ActivityEvent)) == 0
