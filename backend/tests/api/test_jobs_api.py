"""API tests for `/api/jobs` (R2.2-R2.13, R12, design.md §8, §8.1-§8.3)."""

from collections.abc import Callable
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Application, Job, User
from app.repositories.job_repository import JobRepository
from app.repositories.skill_repository import SkillRepository

pytestmark = pytest.mark.api

JOBS_PATH = "/api/jobs"
PAGE_FIELDS = {"items", "total", "page", "page_size", "total_pages"}
SUMMARY_FIELDS = {
    "id",
    "title",
    "company",
    "location",
    "employment_type",
    "work_mode",
    "experience_level",
    "salary_min",
    "salary_max",
    "salary_currency",
    "salary_period",
    "deadline",
    "source",
    "discovered_at",
    "required_skills",
    "preferred_skills",
    "is_bookmarked",
    "is_hidden",
    "application_status",
    "match_score",
}
DETAIL_FIELDS = SUMMARY_FIELDS | {
    "match_explanation",
    "description",
    "application_url",
    "min_education_level",
    "application",
}
MATCH_FIELDS = {
    "job_id",
    "score",
    "algorithm_version",
    "factors",
    "matched_required_skills",
    "missing_required_skills",
    "matched_preferred_skills",
    "missing_preferred_skills",
    "positive_reasons",
    "negative_reasons",
}


@pytest.fixture
def job(db_session: Session, make_job: Callable[..., Job]) -> Job:
    created = make_job(
        deadline=date(2025, 2, 1),
        experience_level="internship",
        salary_min=1000,
        salary_max=1500,
        salary_currency="EUR",
        salary_period="month",
    )
    skills = SkillRepository(db_session).get_or_create_many(
        {"react": "React", "typescript": "TypeScript", "docker": "Docker"}
    )
    JobRepository(db_session).replace_skills(
        created,
        required=[skills["typescript"].id, skills["react"].id],
        preferred=[skills["docker"].id],
    )
    db_session.commit()
    return created


def ids(response_body: dict[str, object]) -> list[object]:
    items = response_body["items"]
    assert isinstance(items, list)
    return [item["id"] for item in items]


def test_get_jobs_returns_page_with_full_summary_shape(
    client: TestClient, demo_user: User, job: Job
) -> None:
    response = client.get(JOBS_PATH)

    assert response.status_code == 200
    assert response.headers["X-Request-ID"]
    body = response.json()
    assert set(body) == PAGE_FIELDS
    assert (body["total"], body["page"], body["page_size"], body["total_pages"]) == (1, 1, 20, 1)
    [item] = body["items"]
    assert set(item) == SUMMARY_FIELDS
    match = client.post(f"{JOBS_PATH}/{job.id}/match").json()
    assert item.pop("match_score") == match["score"]
    assert item == {
        "id": job.id,
        "title": "Frontend Intern",
        "company": "Example Co",
        "location": "Remote",
        "employment_type": "internship",
        "work_mode": "remote",
        "experience_level": "internship",
        "salary_min": 1000,
        "salary_max": 1500,
        "salary_currency": "EUR",
        "salary_period": "month",
        "deadline": "2025-02-01",
        "source": "seed",
        "discovered_at": "2025-01-15T09:30:00Z",
        "required_skills": ["React", "TypeScript"],
        "preferred_skills": ["Docker"],
        "is_bookmarked": False,
        "is_hidden": False,
        "application_status": None,
    }


def test_get_jobs_binds_repeated_and_comma_filters(
    client: TestClient, demo_user: User, job: Job, make_job: Callable[..., Job], db_session: Session
) -> None:
    onsite = make_job("2", work_mode="onsite", title="Backend Intern")
    make_job("3", work_mode="hybrid", employment_type="full_time")
    db_session.commit()

    by_mode = client.get(
        JOBS_PATH,
        params=[("work_mode", "remote"), ("work_mode", "onsite"), ("sort", "discovered_at")],
    )
    by_skill = client.get(JOBS_PATH, params={"skills": "reactjs,go"})
    by_query = client.get(JOBS_PATH, params={"q": "BACKEND", "employment_type": "internship"})

    assert ids(by_mode.json()) == [job.id, onsite.id]
    assert ids(by_skill.json()) == [job.id]
    assert ids(by_query.json()) == [onsite.id]


def test_get_jobs_sort_order_and_pagination(
    client: TestClient, demo_user: User, make_job: Callable[..., Job], db_session: Session
) -> None:
    jobs = [make_job(str(n), title=title) for n, title in enumerate(["b", "c", "a"], start=1)]
    db_session.commit()

    response = client.get(
        JOBS_PATH, params={"sort": "title", "order": "desc", "page": 1, "page_size": 2}
    )
    beyond = client.get(JOBS_PATH, params={"page": 9, "page_size": 2})

    assert ids(response.json()) == [jobs[1].id, jobs[0].id]
    assert response.json()["total_pages"] == 2
    assert beyond.status_code == 200
    assert beyond.json()["items"] == []
    assert (beyond.json()["total"], beyond.json()["total_pages"]) == (3, 2)


@pytest.mark.parametrize(
    ("params", "loc"),
    [
        ({"page": 0}, ["query", "page"]),
        ({"page_size": 0}, ["query", "page_size"]),
        ({"page_size": 101}, ["query", "page_size"]),
        ({"sort": "popularity"}, ["query", "sort"]),
        ({"order": "sideways"}, ["query", "order"]),
        ({"q": "x" * 101}, ["query", "q"]),
        ({"min_score": 101}, ["query", "min_score"]),
        ({"min_score": -1}, ["query", "min_score"]),
        ({"employment_type": "volunteer"}, ["query", "employment_type", 0]),
        ({"source": "linkedin"}, ["query", "source"]),
        ({"bookmarked": "maybe"}, ["query", "bookmarked"]),
        ({"skills": "(,)"}, ["query", "skills"]),
        ({"secret_param": "sneaky-value"}, ["query", "secret_param"]),
    ],
)
def test_get_jobs_invalid_params_return_422_envelope(
    client: TestClient, demo_user: User, params: dict[str, object], loc: list[object]
) -> None:
    response = client.get(JOBS_PATH, params=params)

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert loc in [detail["loc"] for detail in error["details"]]
    assert "sneaky-value" not in response.text
    assert response.headers["X-Request-ID"]


def test_get_job_detail_returns_full_shape_with_application(
    client: TestClient, demo_user: User, job: Job
) -> None:
    applied = client.post(f"{JOBS_PATH}/{job.id}/apply").json()

    response = client.get(f"{JOBS_PATH}/{job.id}")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == DETAIL_FIELDS
    assert body["description"] == "Build UI components."
    assert body["application_url"] == "https://jobs.example.com/1"
    assert body["min_education_level"] is None
    assert body["application_status"] == "Applied"
    assert body["application"] == applied
    assert body["match_explanation"] == client.post(f"{JOBS_PATH}/{job.id}/match").json()
    assert body["match_score"] == body["match_explanation"]["score"]


def test_post_match_returns_explanation_for_current_profile(
    client: TestClient, demo_user: User, job: Job
) -> None:
    response = client.post(f"{JOBS_PATH}/{job.id}/match")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == MATCH_FIELDS
    assert body["job_id"] == job.id
    assert 0 <= body["score"] <= 100
    assert body["missing_required_skills"] == ["React", "TypeScript"]
    assert body["missing_preferred_skills"] == ["Docker"]
    assert [factor["key"] for factor in body["factors"]] == [
        "required_skills",
        "preferred_skills",
        "role_similarity",
        "experience",
        "location",
        "work_mode",
        "education",
        "projects",
    ]


def test_get_jobs_min_score_and_match_score_sort(
    client: TestClient, demo_user: User, job: Job, make_job: Callable[..., Job], db_session: Session
) -> None:
    # No required skills listed: full required-skill credit, so it outranks `job`.
    open_job = make_job("2")
    db_session.commit()
    job_score = client.post(f"{JOBS_PATH}/{job.id}/match").json()["score"]
    open_score = client.post(f"{JOBS_PATH}/{open_job.id}/match").json()["score"]

    listed = client.get(JOBS_PATH).json()
    above = client.get(JOBS_PATH, params={"min_score": job_score + 1}).json()

    assert open_score > job_score
    assert ids(listed) == [open_job.id, job.id]
    assert [item["match_score"] for item in listed["items"]] == [open_score, job_score]
    assert (ids(above), above["total"]) == ([open_job.id], 1)


def test_bookmark_put_delete_are_idempotent_and_reflected_in_list(
    client: TestClient, demo_user: User, job: Job
) -> None:
    path = f"{JOBS_PATH}/{job.id}/bookmark"
    expected_on = {"job_id": job.id, "is_bookmarked": True, "is_hidden": False}

    assert client.put(path).json() == expected_on
    assert client.put(path).json() == expected_on
    assert ids(client.get(JOBS_PATH, params={"bookmarked": "true"}).json()) == [job.id]
    assert client.delete(path).json() == {**expected_on, "is_bookmarked": False}
    assert client.delete(path).status_code == 200
    assert client.get(JOBS_PATH, params={"bookmarked": "true"}).json()["items"] == []


def test_hide_excludes_from_list_but_detail_still_works(
    client: TestClient, demo_user: User, job: Job
) -> None:
    path = f"{JOBS_PATH}/{job.id}/hide"

    hidden = client.put(path)

    assert hidden.status_code == 200
    assert hidden.json() == {"job_id": job.id, "is_bookmarked": False, "is_hidden": True}
    assert client.get(JOBS_PATH).json()["total"] == 0
    assert ids(client.get(JOBS_PATH, params={"include_hidden": "true"}).json()) == [job.id]
    assert client.get(f"{JOBS_PATH}/{job.id}").json()["is_hidden"] is True
    assert client.delete(path).json()["is_hidden"] is False
    assert client.get(JOBS_PATH).json()["total"] == 1


def test_flags_are_scoped_to_the_demo_user_header(
    client: TestClient, demo_user: User, job: Job, db_session: Session
) -> None:
    other = User(name="Other", email="other@example.com")
    db_session.add(other)
    db_session.commit()

    client.put(f"{JOBS_PATH}/{job.id}/hide", headers={"X-Demo-User": "other@example.com"})

    assert client.get(JOBS_PATH).json()["total"] == 1
    assert client.get(JOBS_PATH, headers={"X-Demo-User": "other@example.com"}).json()["total"] == 0


def test_apply_returns_201_then_200_unchanged(
    client: TestClient, demo_user: User, job: Job
) -> None:
    path = f"{JOBS_PATH}/{job.id}/apply"

    created = client.post(path)
    again = client.post(path)

    assert created.status_code == 201
    assert created.json()["status"] == "Applied"
    assert created.json()["applied_at"] == "2025-01-15"
    assert again.status_code == 200
    assert again.json() == created.json()
    assert client.get(JOBS_PATH).json()["items"][0]["application_status"] == "Applied"


def test_apply_moves_saved_application_with_200(
    client: TestClient, demo_user: User, job: Job
) -> None:
    saved = client.post("/api/applications", json={"job_id": job.id}).json()

    response = client.post(f"{JOBS_PATH}/{job.id}/apply")

    assert response.status_code == 200
    assert response.json()["id"] == saved["id"]
    assert response.json()["status"] == "Applied"


def test_apply_from_rejected_returns_409_envelope(
    client: TestClient, demo_user: User, job: Job, db_session: Session
) -> None:
    db_session.add(Application(user_id=demo_user.id, job_id=job.id, status="Rejected"))
    db_session.commit()

    response = client.post(f"{JOBS_PATH}/{job.id}/apply")

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "INVALID_STATUS_TRANSITION",
            "message": "Cannot move from Rejected to Applied",
            "details": {"from": "Rejected", "to": "Applied", "allowed": ["Interested"]},
        }
    }
    assert client.get(f"{JOBS_PATH}/{job.id}").json()["application_status"] == "Rejected"


@pytest.mark.parametrize(
    ("method", "suffix"),
    [
        ("GET", ""),
        ("PUT", "/bookmark"),
        ("DELETE", "/bookmark"),
        ("PUT", "/hide"),
        ("DELETE", "/hide"),
        ("POST", "/apply"),
        ("POST", "/match"),
    ],
)
def test_job_scoped_endpoints_unknown_job_return_404(
    client: TestClient, demo_user: User, method: str, suffix: str
) -> None:
    response = client.request(method, f"{JOBS_PATH}/999{suffix}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert response.headers["X-Request-ID"]


def test_job_id_below_one_returns_422(client: TestClient, demo_user: User) -> None:
    response = client.get(f"{JOBS_PATH}/0")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
