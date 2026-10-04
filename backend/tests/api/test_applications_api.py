"""API tests for `/api/applications` (R5.1-R5.10, R5.12, R12, design.md §8, §8.1-§8.3)."""

from collections.abc import Callable
from datetime import date

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import ActivityEvent, Application, Job, User

pytestmark = pytest.mark.api

APPLICATIONS_PATH = "/api/applications"
META_PATH = "/api/applications/meta"
APPLICATION_FIELDS = {
    "id",
    "job_id",
    "status",
    "applied_at",
    "deadline",
    "interview_date",
    "recruiter_name",
    "recruiter_email",
    "notes",
    "outcome",
    "created_at",
    "updated_at",
    "job",
}


@pytest.fixture
def job(db_session: Session, make_job: Callable[..., Job]) -> Job:
    created = make_job(deadline=date(2025, 2, 1))
    db_session.commit()
    return created


def create(client: TestClient, job_id: int, **fields: object) -> dict[str, object]:
    response = client.post(APPLICATIONS_PATH, json={"job_id": job_id, **fields})
    assert response.status_code == 201, response.text
    body: dict[str, object] = response.json()
    return body


def count(session: Session, model: type) -> int:
    return session.scalar(sa.select(sa.func.count()).select_from(model)) or 0


def test_post_application_returns_201_with_full_shape(
    client: TestClient, demo_user: User, job: Job
) -> None:
    response = client.post(
        APPLICATIONS_PATH,
        json={
            "job_id": job.id,
            "status": "Applied",
            "notes": "Referred by a friend",
            "deadline": "2025-01-31",
            "interview_date": "2025-01-20T15:00:00+01:00",
            "recruiter_name": " Sam Recruiter ",
            "recruiter_email": "Recruiter@Example.com",
            "outcome": "",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert set(body) == APPLICATION_FIELDS
    assert body["status"] == "Applied"
    assert body["applied_at"] == "2025-01-15"
    assert body["deadline"] == "2025-01-31"
    assert body["interview_date"] == "2025-01-20T14:00:00Z"
    assert body["recruiter_name"] == "Sam Recruiter"
    assert body["recruiter_email"] == "recruiter@example.com"
    assert body["outcome"] is None
    assert body["created_at"] == "2025-01-15T09:30:00Z"
    assert body["updated_at"] == "2025-01-15T09:30:00Z"
    assert body["job"] == {
        "id": job.id,
        "title": "Frontend Intern",
        "company": "Example Co",
        "location": "Remote",
        "deadline": "2025-02-01",
    }
    assert response.headers["X-Request-ID"]


def test_post_application_unknown_job_returns_404(client: TestClient, demo_user: User) -> None:
    response = client.post(APPLICATIONS_PATH, json={"job_id": 999})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_post_application_duplicate_returns_409_envelope(
    client: TestClient, demo_user: User, job: Job, db_session: Session
) -> None:
    create(client, job.id)

    response = client.post(APPLICATIONS_PATH, json={"job_id": job.id})

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "DUPLICATE_APPLICATION",
            "message": "An application for this job already exists.",
            "details": None,
        }
    }
    assert count(db_session, Application) == 1


@pytest.mark.parametrize(
    ("payload", "loc"),
    [
        ({"status": "Ghosted"}, ["body", "status"]),
        ({"status": "saved"}, ["body", "status"]),
        ({"secret_field": "sneaky-value"}, ["body", "secret_field"]),
        ({"recruiter_email": "not-an-email"}, ["body", "recruiter_email"]),
        ({"notes": "x" * 5001}, ["body", "notes"]),
    ],
)
def test_post_application_invalid_returns_422(
    client: TestClient,
    demo_user: User,
    job: Job,
    db_session: Session,
    payload: dict[str, object],
    loc: list[object],
) -> None:
    response = client.post(APPLICATIONS_PATH, json={"job_id": job.id, **payload})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert loc in [detail["loc"] for detail in error["details"]]
    assert "sneaky-value" not in response.text
    assert count(db_session, Application) == 0


def test_get_applications_returns_list_with_job_summary(
    client: TestClient, demo_user: User, job: Job
) -> None:
    created = create(client, job.id)

    response = client.get(APPLICATIONS_PATH)

    assert response.status_code == 200
    assert response.json() == [created]


def test_get_applications_status_filter_accepts_repeated_param(
    client: TestClient, demo_user: User, make_job: Callable[..., Job], db_session: Session
) -> None:
    jobs = [make_job(str(n)) for n in range(1, 4)]
    db_session.commit()
    saved = create(client, jobs[0].id)
    offer = create(client, jobs[1].id, status="Offer")
    create(client, jobs[2].id, status="Applied")

    response = client.get(APPLICATIONS_PATH, params=[("status", "Saved"), ("status", "Offer")])

    assert response.status_code == 200
    assert sorted(item["id"] for item in response.json()) == sorted([saved["id"], offer["id"]])


def test_get_applications_unknown_status_filter_returns_422(
    client: TestClient, demo_user: User
) -> None:
    response = client.get(APPLICATIONS_PATH, params={"status": "Ghosted"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_get_applications_excludes_other_users(
    client: TestClient, demo_user: User, job: Job, db_session: Session
) -> None:
    other = User(name="Other", email="other@example.com")
    db_session.add(other)
    db_session.flush()
    db_session.add(Application(user_id=other.id, job_id=job.id, status="Saved"))
    db_session.commit()

    assert client.get(APPLICATIONS_PATH).json() == []


def test_get_meta_returns_exact_statuses_and_transitions(client: TestClient) -> None:
    response = client.get(META_PATH)

    assert response.status_code == 200
    assert response.json() == {
        "statuses": [
            "Saved",
            "Interested",
            "Applied",
            "Assessment",
            "Interview",
            "Rejected",
            "Offer",
            "Withdrawn",
        ],
        "transitions": {
            "Saved": ["Interested", "Applied", "Withdrawn"],
            "Interested": ["Saved", "Applied", "Withdrawn"],
            "Applied": ["Assessment", "Interview", "Rejected", "Offer", "Withdrawn"],
            "Assessment": ["Interview", "Rejected", "Offer", "Withdrawn"],
            "Interview": ["Assessment", "Rejected", "Offer", "Withdrawn"],
            "Rejected": ["Interested"],
            "Offer": ["Withdrawn"],
            "Withdrawn": ["Interested"],
        },
    }
    assert response.headers["X-Request-ID"]


def test_patch_application_allowed_move_returns_200(
    client: TestClient, demo_user: User, job: Job
) -> None:
    created = create(client, job.id)

    response = client.patch(f"{APPLICATIONS_PATH}/{created['id']}", json={"status": "Applied"})

    assert response.status_code == 200
    body = response.json()
    assert set(body) == APPLICATION_FIELDS
    assert body["status"] == "Applied"
    assert body["applied_at"] == "2025-01-15"


def test_patch_application_disallowed_move_returns_409_with_details(
    client: TestClient, demo_user: User, job: Job
) -> None:
    created = create(client, job.id, status="Offer")
    path = f"{APPLICATIONS_PATH}/{created['id']}"

    response = client.patch(path, json={"status": "Applied"})

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "INVALID_STATUS_TRANSITION",
            "message": "Cannot move from Offer to Applied",
            "details": {"from": "Offer", "to": "Applied", "allowed": ["Withdrawn"]},
        }
    }
    assert client.get(APPLICATIONS_PATH).json()[0]["status"] == "Offer"


@pytest.mark.parametrize(
    ("payload", "loc"),
    [
        ({"status": "Ghosted"}, ["body", "status"]),
        ({"status": None}, ["body", "status"]),
        ({"notes": None}, ["body", "notes"]),
        ({"job_id": 2}, ["body", "job_id"]),
    ],
)
def test_patch_application_invalid_returns_422(
    client: TestClient,
    demo_user: User,
    job: Job,
    payload: dict[str, object],
    loc: list[object],
) -> None:
    created = create(client, job.id)

    response = client.patch(f"{APPLICATIONS_PATH}/{created['id']}", json=payload)

    assert response.status_code == 422
    assert loc in [detail["loc"] for detail in response.json()["error"]["details"]]
    assert client.get(APPLICATIONS_PATH).json() == [created]


def test_patch_application_explicit_null_clears_field(
    client: TestClient, demo_user: User, job: Job
) -> None:
    created = create(client, job.id, recruiter_name="Sam", outcome="Pending")

    response = client.patch(f"{APPLICATIONS_PATH}/{created['id']}", json={"recruiter_name": None})

    body = response.json()
    assert body["recruiter_name"] is None
    assert body["outcome"] == "Pending"


def test_patch_unknown_application_returns_404(client: TestClient, demo_user: User) -> None:
    response = client.patch(f"{APPLICATIONS_PATH}/999", json={"notes": "x"})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_patch_application_id_below_one_returns_422(client: TestClient, demo_user: User) -> None:
    response = client.patch(f"{APPLICATIONS_PATH}/0", json={"notes": "x"})

    assert response.status_code == 422


def test_delete_application_returns_204_then_404(
    client: TestClient, demo_user: User, job: Job, db_session: Session
) -> None:
    created = create(client, job.id)
    path = f"{APPLICATIONS_PATH}/{created['id']}"

    response = client.delete(path)

    assert response.status_code == 204
    assert response.content == b""
    assert response.headers["X-Request-ID"]
    assert client.delete(path).status_code == 404
    types = list(db_session.scalars(sa.select(ActivityEvent.type).order_by(ActivityEvent.id)))
    assert types == ["application_created", "application_deleted"]
