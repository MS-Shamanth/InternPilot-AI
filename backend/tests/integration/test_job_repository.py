"""JobRepository against a real session (design.md §3.3, §8; R2.3, R2.4)."""

from collections.abc import Callable

import pytest
from sqlalchemy.orm import Session

from app.models import Job, User
from app.repositories.job_repository import JobRepository, JobSearchFilters, escape_like
from app.repositories.job_state_repository import JobStateRepository
from app.repositories.skill_repository import SkillRepository

pytestmark = pytest.mark.integration

UserFactory = Callable[..., User]
JobFactory = Callable[..., Job]


def ids(jobs: list[Job]) -> list[int]:
    return [job.id for job in jobs]


@pytest.fixture
def user(make_user: UserFactory) -> User:
    return make_user()


def search(session: Session, user: User, **filters: object) -> list[int]:
    return ids(JobRepository(session).search(user.id, JobSearchFilters(**filters)))


# --- lookups ------------------------------------------------------------------------------


def test_get_by_id_loads_skills(db_session: Session, make_job: JobFactory) -> None:
    job = make_job()
    skills = SkillRepository(db_session).get_or_create_many({"react": "React"})
    repository = JobRepository(db_session)
    repository.replace_skills(job, required=[skills["react"].id])
    db_session.expire_all()

    loaded = repository.get_by_id(job.id)

    assert loaded is not None
    assert [link.skill.normalized_name for link in loaded.job_skills] == ["react"]
    assert repository.get_by_id(job.id + 100) is None


def test_get_by_source_external_id_and_fingerprint(
    db_session: Session, make_job: JobFactory
) -> None:
    job = make_job("7", source="remotive")
    repository = JobRepository(db_session)

    assert repository.get_by_source_external_id("remotive", "ext-7") is job
    assert repository.get_by_source_external_id("seed", "ext-7") is None
    assert repository.get_by_fingerprint("7".rjust(64, "0")) is job
    assert repository.get_by_fingerprint("8".rjust(64, "0")) is None


def test_count_all_and_list_by_ids(db_session: Session, make_job: JobFactory) -> None:
    first, second, _third = make_job("1"), make_job("2"), make_job("3")
    repository = JobRepository(db_session)

    assert repository.count_all() == 3
    assert ids(repository.list_by_ids([second.id, first.id, 999])) == [first.id, second.id]
    assert repository.list_by_ids([]) == []


def test_replace_skills_required_wins_over_preferred(
    db_session: Session, make_job: JobFactory
) -> None:
    job = make_job()
    skills = SkillRepository(db_session).get_or_create_many(
        {"react": "React", "css": "CSS", "sql": "SQL"}
    )
    repository = JobRepository(db_session)
    repository.replace_skills(job, required=[skills["sql"].id], preferred=[skills["css"].id])

    repository.replace_skills(
        job, required=[skills["react"].id], preferred=[skills["react"].id, skills["css"].id]
    )

    db_session.expire_all()
    loaded = repository.get_by_id(job.id)
    assert loaded is not None
    assert {link.skill.normalized_name: link.is_required for link in loaded.job_skills} == {
        "react": True,
        "css": False,
    }


# --- search -------------------------------------------------------------------------------


def test_escape_like_escapes_wildcards_and_escape_char() -> None:
    assert escape_like(r"50%_a\b") == r"50\%\_a\\b"


@pytest.mark.parametrize("q", ["REACT", "acme", "graphql"])
def test_search_q_matches_title_company_description_case_insensitively(
    db_session: Session, user: User, make_job: JobFactory, q: str
) -> None:
    match = {
        "REACT": {"title": "React Intern"},
        "acme": {"company": "ACME Labs"},
        "graphql": {"description": "Work with GraphQL APIs."},
    }[q]
    expected = make_job("1", **match)
    make_job("2")

    assert search(db_session, user, q=q) == [expected.id]


def test_search_q_wildcards_are_literal(
    db_session: Session, user: User, make_job: JobFactory
) -> None:
    percent = make_job("1", title="100% Remote Intern")
    underscore = make_job("2", title="snake_case Developer")
    make_job("3", title="100 Remote Intern")
    make_job("4", title="snakeXcase Developer")

    assert search(db_session, user, q="%") == [percent.id]
    assert search(db_session, user, q="e_c") == [underscore.id]


def test_search_enum_filters_match_any_value(
    db_session: Session, user: User, make_job: JobFactory
) -> None:
    intern = make_job("1", employment_type="internship", work_mode="remote")
    full_time = make_job("2", employment_type="full_time", work_mode="hybrid")
    make_job("3", employment_type="contract", work_mode="onsite")

    assert search(db_session, user, employment_types=("internship", "full_time")) == [
        intern.id,
        full_time.id,
    ]
    assert search(db_session, user, work_modes=("hybrid",)) == [full_time.id]


def test_search_experience_level_filter(
    db_session: Session, user: User, make_job: JobFactory
) -> None:
    junior = make_job("1", experience_level="junior")
    make_job("2", experience_level="senior")
    make_job("3")

    assert search(db_session, user, experience_levels=("junior",)) == [junior.id]


def test_search_location_substring_and_source(
    db_session: Session, user: User, make_job: JobFactory
) -> None:
    berlin = make_job("1", location="Berlin, Germany", source="arbeitnow")
    remote = make_job("2", location="Remote", source="remotive")

    assert search(db_session, user, location="berlin") == [berlin.id]
    assert search(db_session, user, source="remotive") == [remote.id]


def test_search_filters_combine_with_and(
    db_session: Session, user: User, make_job: JobFactory
) -> None:
    both = make_job("1", title="React Intern", work_mode="remote")
    make_job("2", title="React Intern", work_mode="onsite")
    make_job("3", title="Data Intern", work_mode="remote")

    assert search(db_session, user, q="react", work_modes=("remote",)) == [both.id]


def test_search_skills_filter_matches_any_skill(
    db_session: Session, user: User, make_job: JobFactory
) -> None:
    react_job, sql_job, go_job = make_job("1"), make_job("2"), make_job("3")
    skills = SkillRepository(db_session).get_or_create_many(
        {"react": "React", "sql": "SQL", "go": "Go"}
    )
    repository = JobRepository(db_session)
    repository.replace_skills(react_job, required=[skills["react"].id])
    repository.replace_skills(sql_job, required=[], preferred=[skills["sql"].id])
    repository.replace_skills(go_job, required=[skills["go"].id])

    assert search(db_session, user, skills=("react", "sql")) == [react_job.id, sql_job.id]


def test_search_excludes_hidden_only_for_that_user(
    db_session: Session, user: User, make_user: UserFactory, make_job: JobFactory
) -> None:
    other = make_user(email="other@example.com")
    hidden, visible = make_job("1"), make_job("2")
    states = JobStateRepository(db_session)
    states.get_or_create(user.id, hidden.id).is_hidden = True
    states.get_or_create(other.id, visible.id).is_hidden = True
    db_session.flush()

    assert search(db_session, user) == [visible.id]
    assert search(db_session, user, include_hidden=True) == [hidden.id, visible.id]
    assert search(db_session, other) == [hidden.id]


def test_search_bookmarked_only_for_that_user(
    db_session: Session, user: User, make_user: UserFactory, make_job: JobFactory
) -> None:
    other = make_user(email="other@example.com")
    mine, theirs, _plain = make_job("1"), make_job("2"), make_job("3")
    states = JobStateRepository(db_session)
    states.get_or_create(user.id, mine.id).is_bookmarked = True
    states.get_or_create(other.id, theirs.id).is_bookmarked = True
    db_session.flush()

    assert search(db_session, user, bookmarked_only=True) == [mine.id]
    assert search(db_session, other, bookmarked_only=True) == [theirs.id]


def test_search_returns_jobs_with_skills_loaded(
    db_session: Session, user: User, make_job: JobFactory
) -> None:
    job = make_job()
    skills = SkillRepository(db_session).get_or_create_many({"react": "React"})
    JobRepository(db_session).replace_skills(job, required=[skills["react"].id])
    db_session.expire_all()

    [found] = JobRepository(db_session).search(user.id, JobSearchFilters())

    assert "job_skills" in found.__dict__
    assert [link.skill.name for link in found.job_skills] == ["React"]
