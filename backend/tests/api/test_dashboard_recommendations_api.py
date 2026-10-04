"""API tests for `/api/recommendations` (R7.1-R7.3) and `/api/dashboard` (R6.1-R6.5)."""

from collections.abc import Callable
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Application, Job, User, UserJobState
from app.repositories.activity_repository import ActivityRepository
from app.repositories.job_repository import JobRepository
from app.repositories.skill_repository import SkillRepository
from tests.conftest import FIXED_NOW

pytestmark = pytest.mark.api

TODAY = FIXED_NOW.date()
DASHBOARD_FIELDS = {
    "total_jobs_discovered",
    "matching_jobs",
    "applications_submitted",
    "interviews_scheduled",
    "offers_received",
    "response_rate",
    "upcoming_deadlines",
    "recent_activity",
    "top_recommendations",
    "status_breakdown",
    "applications_over_time",
    "score_distribution",
}


@pytest.fixture
def jobs(db_session: Session, make_job: Callable[..., Job], demo_user: User) -> list[Job]:
    """Five jobs: `low` requires a skill the empty profile lacks, so it scores lowest."""
    early = make_job("1", deadline=TODAY + timedelta(days=2))
    late = make_job("2", deadline=TODAY + timedelta(days=5))
    no_deadline = make_job("3")
    low = make_job("4", deadline=TODAY + timedelta(days=1))
    applied = make_job("5", deadline=TODAY + timedelta(days=3))
    react = SkillRepository(db_session).get_or_create_many({"react": "React"})["react"]
    JobRepository(db_session).replace_skills(low, required=[react.id])
    db_session.commit()
    return [early, late, no_deadline, low, applied]


def add_application(
    db_session: Session, user: User, job: Job, status: str, **values: object
) -> Application:
    record = Application(user_id=user.id, job_id=job.id, status=status, **values)
    db_session.add(record)
    db_session.commit()
    return record


def test_recommendations_order_by_score_deadline_id(client: TestClient, jobs: list[Job]) -> None:
    response = client.get("/api/recommendations", params={"limit": 20})
    assert response.status_code == 200
    body = response.json()
    assert [item["job"]["id"] for item in body] == [
        jobs[0].id,
        jobs[4].id,
        jobs[1].id,
        jobs[2].id,
        jobs[3].id,
    ]
    first = body[0]
    assert first["match_explanation"]["job_id"] == jobs[0].id
    assert first["job"]["match_score"] == first["match_explanation"]["score"]
    assert body[-1]["job"]["match_score"] < first["job"]["match_score"]


def test_recommendations_exclude_hidden_and_submitted_jobs(
    client: TestClient, db_session: Session, demo_user: User, jobs: list[Job]
) -> None:
    db_session.add(UserJobState(user_id=demo_user.id, job_id=jobs[1].id, is_hidden=True))
    add_application(db_session, demo_user, jobs[4], "Applied")
    add_application(db_session, demo_user, jobs[0], "Interested")
    body = client.get("/api/recommendations", params={"limit": 20}).json()
    ids = [item["job"]["id"] for item in body]
    assert ids == [jobs[0].id, jobs[2].id, jobs[3].id]
    assert body[0]["job"]["application_status"] == "Interested"


def test_recommendations_default_limit_is_five(
    client: TestClient, make_job: Callable[..., Job], db_session: Session, demo_user: User
) -> None:
    for index in range(7):
        make_job(str(index))
    db_session.commit()
    assert len(client.get("/api/recommendations").json()) == 5


@pytest.mark.parametrize("limit", [0, 21, "x"])
def test_recommendations_limit_out_of_range_returns_422(
    client: TestClient, demo_user: User, limit: object
) -> None:
    response = client.get("/api/recommendations", params={"limit": limit})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_dashboard_empty_returns_zeros_and_empty_lists(client: TestClient, demo_user: User) -> None:
    response = client.get("/api/dashboard")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == DASHBOARD_FIELDS
    assert body["total_jobs_discovered"] == 0
    assert body["response_rate"] == 0.0
    assert (
        body["upcoming_deadlines"] == body["recent_activity"] == body["top_recommendations"] == []
    )
    assert len(body["status_breakdown"]) == 8
    assert all(item["count"] == 0 for item in body["status_breakdown"])
    assert len(body["applications_over_time"]) == 8
    assert [item["bucket"] for item in body["score_distribution"]] == [
        "0-19",
        "20-39",
        "40-59",
        "60-79",
        "80-100",
    ]


def test_dashboard_reflects_current_data(
    client: TestClient, db_session: Session, demo_user: User, jobs: list[Job]
) -> None:
    db_session.add(UserJobState(user_id=demo_user.id, job_id=jobs[1].id, is_bookmarked=True))
    add_application(db_session, demo_user, jobs[4], "Applied", applied_at=TODAY)
    interview = add_application(
        db_session, demo_user, jobs[0], "Interview", applied_at=date(2025, 1, 6)
    )
    ActivityRepository(db_session).add(
        demo_user.id, "status_changed", "Moved", job_id=jobs[0].id, application_id=interview.id
    )
    db_session.commit()

    body = client.get("/api/dashboard").json()

    assert body["total_jobs_discovered"] == 5
    assert body["applications_submitted"] == 2
    assert body["interviews_scheduled"] == 1
    assert body["offers_received"] == 0
    assert body["response_rate"] == 50.0
    assert [(d["job_id"], d["kind"], d["days_left"]) for d in body["upcoming_deadlines"]] == [
        (jobs[0].id, "application", 2),
        (jobs[4].id, "application", 3),
        (jobs[1].id, "bookmark", 5),
    ]
    assert body["recent_activity"][0]["type"] == "status_changed"
    assert body["recent_activity"][0]["created_at"].endswith("Z")
    assert body["top_recommendations"][0]["job_id"] == jobs[1].id
    assert set(body["top_recommendations"][0]) == {
        "job_id",
        "title",
        "company",
        "location",
        "score",
    }
    counts = {item["status"]: item["count"] for item in body["status_breakdown"]}
    assert (counts["Applied"], counts["Interview"]) == (1, 1)
    assert [w["count"] for w in body["applications_over_time"]][-2:] == [1, 1]
    assert sum(item["count"] for item in body["score_distribution"]) == 5
    assert body["matching_jobs"] == sum(
        item["count"]
        for item in body["score_distribution"]
        if item["bucket"] in {"60-79", "80-100"}
    )
