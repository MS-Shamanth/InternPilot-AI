"""JobService against a real session (R2.2-R2.12, design.md §3.3, §8)."""

from collections.abc import Callable
from datetime import UTC, date, datetime

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.clock import FixedClock
from app.core.errors import InvalidStatusTransitionError, NotFoundError
from app.models import ActivityEvent, Application, Job, User, UserJobState, UserSkill
from app.repositories.job_repository import JobRepository
from app.repositories.skill_repository import SkillRepository
from app.schemas.job import JobListParams, JobState
from app.services.application_status import ApplicationStatus
from app.services.job_service import JobService

pytestmark = pytest.mark.integration

UserFactory = Callable[..., User]
JobFactory = Callable[..., Job]


@pytest.fixture
def user(make_user: UserFactory) -> User:
    return make_user()


@pytest.fixture
def other_user(make_user: UserFactory) -> User:
    return make_user("other@example.com")


@pytest.fixture
def service(db_session: Session, fixed_clock: FixedClock) -> JobService:
    return JobService(db_session, fixed_clock)


def add_skills(
    session: Session, job: Job, required: tuple[str, ...] = (), preferred: tuple[str, ...] = ()
) -> None:
    names = {name.lower(): name for name in (*required, *preferred)}
    skills = SkillRepository(session).get_or_create_many(names)
    JobRepository(session).replace_skills(
        job,
        required=[skills[name.lower()].id for name in required],
        preferred=[skills[name.lower()].id for name in preferred],
    )


def listed_ids(service: JobService, user: User, **params: object) -> list[int]:
    page = service.list_jobs(user, JobListParams.model_validate(params))
    return [item.id for item in page.items]


def event_types(session: Session) -> list[str]:
    return list(session.scalars(sa.select(ActivityEvent.type).order_by(ActivityEvent.id)))


# --- list: search and filters -------------------------------------------------------------


def test_list_jobs_q_matches_title_company_or_description_case_insensitively(
    service: JobService, user: User, make_job: JobFactory
) -> None:
    by_title = make_job("1", title="React Developer Intern")
    by_company = make_job("2", company="ReactLabs")
    by_description = make_job("3", description="You will write REACT hooks.")
    make_job("4", title="Data Analyst", description="SQL reports.")

    # Sorted by title: "Frontend Intern" (ids 2, 3) before "React Developer Intern".
    assert listed_ids(service, user, q="react", sort="title") == [
        by_company.id,
        by_description.id,
        by_title.id,
    ]


@pytest.mark.parametrize(
    ("params", "expected_suffixes"),
    [
        ({"employment_type": ["full_time"]}, ["2"]),
        ({"employment_type": ["full_time", "contract"]}, ["2", "3"]),
        ({"work_mode": ["onsite"]}, ["3"]),
        ({"work_mode": ["hybrid", "onsite"]}, ["2", "3"]),
        ({"experience_level": ["junior"]}, ["2"]),
        ({"experience_level": ["junior", "mid"]}, ["2", "3"]),
        ({"location": "berlin"}, ["2"]),
        ({"source": "remotive"}, ["3"]),
        ({"skills": "ReactJS"}, ["1"]),
        ({"skills": "postgres, react"}, ["1", "2"]),
        ({"employment_type": ["full_time", "contract"], "work_mode": ["onsite"]}, ["3"]),
        ({"work_mode": ["hybrid", "onsite"], "skills": "postgresql"}, ["2"]),
    ],
)
def test_list_jobs_filters_match_all_filters_and_any_value(
    service: JobService,
    user: User,
    make_job: JobFactory,
    db_session: Session,
    params: dict[str, object],
    expected_suffixes: list[str],
) -> None:
    jobs = {
        "1": make_job("1", experience_level="internship"),
        "2": make_job(
            "2",
            employment_type="full_time",
            work_mode="hybrid",
            experience_level="junior",
            location="Berlin, Germany",
        ),
        "3": make_job(
            "3",
            employment_type="contract",
            work_mode="onsite",
            experience_level="mid",
            source="remotive",
        ),
    }
    add_skills(db_session, jobs["1"], required=("React",))
    add_skills(db_session, jobs["2"], preferred=("PostgreSQL",))

    assert listed_ids(service, user, sort="title", **params) == [
        jobs[suffix].id for suffix in expected_suffixes
    ]


def test_list_jobs_bookmarked_only_is_scoped_to_user(
    service: JobService, user: User, other_user: User, make_job: JobFactory
) -> None:
    mine, theirs, _plain = make_job("1"), make_job("2"), make_job("3")
    service.bookmark(user, mine.id)
    service.bookmark(other_user, theirs.id)

    assert listed_ids(service, user, bookmarked=True) == [mine.id]


def test_list_jobs_excludes_hidden_unless_include_hidden(
    service: JobService, user: User, other_user: User, make_job: JobFactory
) -> None:
    visible, hidden = make_job("1"), make_job("2")
    service.hide(user, hidden.id)

    assert listed_ids(service, user) == [visible.id]
    assert listed_ids(service, other_user) == [visible.id, hidden.id]
    page = service.list_jobs(user, JobListParams(include_hidden=True))
    assert [(item.id, item.is_hidden) for item in page.items] == [
        (visible.id, False),
        (hidden.id, True),
    ]
    assert service.get_detail(user, hidden.id).is_hidden is True


# --- list: sorting ------------------------------------------------------------------------


@pytest.fixture
def sortable_jobs(make_job: JobFactory) -> dict[str, Job]:
    """Jobs with ties and nulls on every non-score key; created in id order a, b, c, d."""
    return {
        "a": make_job(
            "a",
            title="beta",
            company="Zeta",
            deadline=date(2025, 3, 1),
            salary_max=3000,
            discovered_at=datetime(2025, 1, 2, tzinfo=UTC),
        ),
        "b": make_job(
            "b",
            title="Alpha",
            company="zeta",
            deadline=None,
            salary_min=4000,
            discovered_at=datetime(2025, 1, 3, tzinfo=UTC),
        ),
        "c": make_job(
            "c",
            title="Beta",
            company="Acme",
            deadline=date(2025, 2, 1),
            discovered_at=datetime(2025, 1, 2, tzinfo=UTC),
        ),
        "d": make_job(
            "d",
            title="gamma",
            company="acme",
            deadline=date(2025, 2, 1),
            salary_min=1000,
            salary_max=3000,
            discovered_at=datetime(2025, 1, 1, tzinfo=UTC),
        ),
    }


@pytest.mark.parametrize(
    ("sort", "order", "expected"),
    [
        ("discovered_at", None, "bacd"),
        ("discovered_at", "desc", "bacd"),
        ("discovered_at", "asc", "dacb"),
        ("deadline", None, "cdab"),
        ("deadline", "asc", "cdab"),
        ("deadline", "desc", "acdb"),
        ("title", None, "bacd"),
        ("title", "asc", "bacd"),
        ("title", "desc", "dacb"),
        ("company", None, "cdab"),
        ("company", "asc", "cdab"),
        ("company", "desc", "abcd"),
        ("salary", None, "badc"),
        ("salary", "desc", "badc"),
        ("salary", "asc", "adbc"),
    ],
)
def test_list_jobs_sorts_with_id_tie_break_and_nulls_last(
    service: JobService,
    user: User,
    sortable_jobs: dict[str, Job],
    sort: str,
    order: str | None,
    expected: str,
) -> None:
    params: dict[str, object] = {"sort": sort}
    if order is not None:
        params["order"] = order

    assert listed_ids(service, user, **params) == [sortable_jobs[key].id for key in expected]


@pytest.fixture
def scored_jobs(user: User, make_job: JobFactory, db_session: Session) -> dict[str, Job]:
    """The user knows Python; "high" requires it, "mid" half of its skills, "low" none.

    "tie" duplicates "high" with a larger id. Created in id order low, high, mid, tie.
    """
    skill = SkillRepository(db_session).get_or_create_many({"python": "Python"})["python"]
    db_session.add(UserSkill(user_id=user.id, skill_id=skill.id))
    jobs = {key: make_job(key) for key in ("low", "high", "mid", "tie")}
    add_skills(db_session, jobs["low"], required=("Java",))
    add_skills(db_session, jobs["high"], required=("Python",))
    add_skills(db_session, jobs["mid"], required=("Python", "Java"))
    add_skills(db_session, jobs["tie"], required=("Python",))
    db_session.flush()
    return jobs


def test_list_jobs_default_sort_is_match_score_desc_with_id_tie_break(
    service: JobService, user: User, scored_jobs: dict[str, Job]
) -> None:
    expected = [scored_jobs[key].id for key in ("high", "tie", "mid", "low")]

    assert listed_ids(service, user) == expected
    assert listed_ids(service, user, sort="match_score", order="asc") == [
        scored_jobs[key].id for key in ("low", "mid", "high", "tie")
    ]


def test_list_jobs_scores_equal_detail_and_match_endpoint(
    service: JobService, user: User, scored_jobs: dict[str, Job]
) -> None:
    """R3.12: list, detail and match show the same score for a (profile, job) pair."""
    page = service.list_jobs(user, JobListParams())

    for item in page.items:
        detail = service.get_detail(user, item.id)
        assert item.match_score == detail.match_score == detail.match_explanation.score
        assert service.match(user, item.id) == detail.match_explanation
    scores = {item.id: item.match_score for item in page.items}
    assert scores[scored_jobs["high"].id] > scores[scored_jobs["mid"].id]
    assert scores[scored_jobs["mid"].id] > scores[scored_jobs["low"].id]


def test_list_jobs_min_score_filters_before_pagination(
    service: JobService, user: User, scored_jobs: dict[str, Job]
) -> None:
    threshold = service.match(user, scored_jobs["mid"].id).score

    page = service.list_jobs(user, JobListParams(min_score=threshold, page_size=2))
    second = service.list_jobs(user, JobListParams(min_score=threshold, page=2, page_size=2))

    assert [item.id for item in page.items] == [scored_jobs["high"].id, scored_jobs["tie"].id]
    assert [item.id for item in second.items] == [scored_jobs["mid"].id]
    assert (page.total, page.total_pages) == (3, 2)
    assert service.list_jobs(user, JobListParams(min_score=100)).total == 0


def test_match_explanation_lists_matched_and_missing_skills(
    service: JobService, user: User, scored_jobs: dict[str, Job]
) -> None:
    explanation = service.match(user, scored_jobs["mid"].id)

    assert explanation.job_id == scored_jobs["mid"].id
    assert explanation.matched_required_skills == ["Python"]
    assert explanation.missing_required_skills == ["Java"]
    assert len(explanation.factors) == 8


# --- list: pagination and per-user fields -------------------------------------------------


def test_list_jobs_paginates_and_reports_totals(
    service: JobService, user: User, make_job: JobFactory
) -> None:
    jobs = [make_job(str(n)) for n in range(1, 6)]

    second = service.list_jobs(user, JobListParams(sort="title", page=2, page_size=2))
    last = service.list_jobs(user, JobListParams(sort="title", page=3, page_size=2))

    assert [item.id for item in second.items] == [jobs[2].id, jobs[3].id]
    assert (second.total, second.page, second.page_size, second.total_pages) == (5, 2, 2, 3)
    assert [item.id for item in last.items] == [jobs[4].id]


def test_list_jobs_page_beyond_last_is_empty_with_correct_totals(
    service: JobService, user: User, make_job: JobFactory
) -> None:
    make_job("1")
    make_job("2")

    page = service.list_jobs(user, JobListParams(page=5, page_size=1))

    assert page.items == []
    assert (page.total, page.page, page.total_pages) == (2, 5, 2)


def test_list_jobs_empty_has_zero_pages(service: JobService, user: User) -> None:
    page = service.list_jobs(user, JobListParams())

    assert (page.items, page.total, page.total_pages) == ([], 0, 0)


def test_list_jobs_summary_has_flags_status_and_sorted_skills(
    service: JobService,
    user: User,
    other_user: User,
    make_job: JobFactory,
    db_session: Session,
) -> None:
    job = make_job(
        "1", salary_min=1000, salary_max=2000, salary_currency="EUR", salary_period="month"
    )
    add_skills(db_session, job, required=("TypeScript", "React"), preferred=("Docker", "AWS"))
    service.bookmark(user, job.id)
    db_session.add(Application(user_id=user.id, job_id=job.id, status="Interview"))
    db_session.add(Application(user_id=other_user.id, job_id=job.id, status="Offer"))
    db_session.flush()

    [summary] = service.list_jobs(user, JobListParams()).items
    [other_summary] = service.list_jobs(other_user, JobListParams()).items

    assert summary.required_skills == ["React", "TypeScript"]
    assert summary.preferred_skills == ["AWS", "Docker"]
    assert (summary.is_bookmarked, summary.is_hidden) == (True, False)
    assert summary.application_status is ApplicationStatus.INTERVIEW
    assert (summary.salary_currency, summary.salary_period) == ("EUR", "month")
    assert other_summary.is_bookmarked is False
    assert other_summary.application_status is ApplicationStatus.OFFER


# --- detail -------------------------------------------------------------------------------


def test_get_detail_includes_description_url_education_and_application(
    service: JobService, user: User, make_job: JobFactory, db_session: Session
) -> None:
    job = make_job("1", min_education_level="bachelor")
    db_session.add(Application(user_id=user.id, job_id=job.id, status="Saved", notes="Ask Sam"))
    db_session.flush()

    detail = service.get_detail(user, job.id)

    assert detail.description == "Build UI components."
    assert detail.application_url == "https://jobs.example.com/1"
    assert detail.min_education_level == "bachelor"
    assert detail.application is not None
    assert (detail.application.status, detail.application.notes) == ("Saved", "Ask Sam")
    assert detail.application_status is ApplicationStatus.SAVED


def test_get_detail_without_application_or_state(
    service: JobService, user: User, make_job: JobFactory
) -> None:
    detail = service.get_detail(user, make_job("1").id)

    assert detail.application is None
    assert detail.application_status is None
    assert (detail.is_bookmarked, detail.is_hidden) == (False, False)


def test_get_detail_unknown_job_raises_not_found(service: JobService, user: User) -> None:
    with pytest.raises(NotFoundError):
        service.get_detail(user, 999)


# --- bookmark / hide ----------------------------------------------------------------------


def test_bookmark_is_idempotent_and_records_one_event(
    service: JobService,
    user: User,
    make_job: JobFactory,
    db_session: Session,
    fixed_clock: FixedClock,
) -> None:
    job = make_job("1", title="Data Intern", company="Acme")

    first = service.bookmark(user, job.id)
    second = service.bookmark(user, job.id)

    expected = JobState(job_id=job.id, is_bookmarked=True, is_hidden=False)
    assert first == second == expected
    events = list(db_session.scalars(sa.select(ActivityEvent)))
    assert [(event.type, event.message, event.job_id) for event in events] == [
        ("job_bookmarked", "Bookmarked Data Intern at Acme", job.id)
    ]
    assert events[0].created_at == fixed_clock.now()


def test_unbookmark_clears_flag_without_event_and_is_idempotent(
    service: JobService, user: User, make_job: JobFactory, db_session: Session
) -> None:
    job = make_job("1")
    service.bookmark(user, job.id)

    assert service.unbookmark(user, job.id).is_bookmarked is False
    assert service.unbookmark(user, job.id).is_bookmarked is False
    assert event_types(db_session) == ["job_bookmarked"]


def test_unset_flags_without_state_row_create_nothing(
    service: JobService, user: User, make_job: JobFactory, db_session: Session
) -> None:
    job = make_job("1")

    assert service.unbookmark(user, job.id) == JobState(
        job_id=job.id, is_bookmarked=False, is_hidden=False
    )
    assert service.unhide(user, job.id).is_hidden is False
    assert db_session.scalar(sa.select(sa.func.count()).select_from(UserJobState)) == 0
    assert event_types(db_session) == []


def test_hide_and_unhide_keep_bookmark_and_are_scoped_to_user(
    service: JobService, user: User, other_user: User, make_job: JobFactory, db_session: Session
) -> None:
    job = make_job("1")
    service.bookmark(user, job.id)

    hidden = service.hide(user, job.id)
    service.hide(user, job.id)

    assert hidden == JobState(job_id=job.id, is_bookmarked=True, is_hidden=True)
    assert service.get_detail(other_user, job.id).is_hidden is False
    assert service.unhide(user, job.id) == JobState(
        job_id=job.id, is_bookmarked=True, is_hidden=False
    )
    assert event_types(db_session) == ["job_bookmarked", "job_hidden"]


@pytest.mark.parametrize("action", ["bookmark", "unbookmark", "hide", "unhide", "apply", "match"])
def test_job_scoped_actions_unknown_job_raise_not_found(
    service: JobService, user: User, action: str
) -> None:
    with pytest.raises(NotFoundError):
        getattr(service, action)(user, 999)


# --- apply --------------------------------------------------------------------------------


def test_apply_creates_application_then_returns_it_unchanged(
    service: JobService, user: User, make_job: JobFactory
) -> None:
    job = make_job("1")

    created = service.apply(user, job.id)
    again = service.apply(user, job.id)

    assert created.created is True
    assert created.application.status is ApplicationStatus.APPLIED
    assert created.application.applied_at == date(2025, 1, 15)
    assert again.created is False
    assert again.application == created.application


def test_apply_moves_interested_to_applied(
    service: JobService, user: User, make_job: JobFactory, db_session: Session
) -> None:
    job = make_job("1")
    db_session.add(Application(user_id=user.id, job_id=job.id, status="Interested"))
    db_session.flush()

    result = service.apply(user, job.id)

    assert result.created is False
    assert result.application.status is ApplicationStatus.APPLIED


def test_apply_from_offer_raises_and_leaves_application(
    service: JobService, user: User, make_job: JobFactory, db_session: Session
) -> None:
    job = make_job("1")
    db_session.add(Application(user_id=user.id, job_id=job.id, status="Offer"))
    db_session.commit()

    with pytest.raises(InvalidStatusTransitionError):
        service.apply(user, job.id)

    assert db_session.scalar(sa.select(Application.status)) == "Offer"
