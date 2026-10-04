"""API tests for `GET/PUT /api/profile` (R1.1-R1.7, R12, design.md §8, §8.1, §8.3)."""

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import ActivityEvent, Skill, User, UserSkill

pytestmark = pytest.mark.api

PROFILE_PATH = "/api/profile"
PROFILE_FIELDS = {
    "id",
    "name",
    "email",
    "location",
    "target_roles",
    "preferred_locations",
    "preferred_work_modes",
    "experience_level",
    "education_level",
    "education",
    "technical_skills",
    "soft_skills",
    "projects",
    "certifications",
    "resume_text",
    "github_url",
    "portfolio_url",
    "linkedin_url",
    "created_at",
    "updated_at",
}

FULL_PROFILE: dict[str, object] = {
    "name": "Ada Student",
    "email": "Ada@Example.org",
    "location": "Berlin, Germany",
    "target_roles": ["Frontend Engineer", "frontend engineer", "Data Analyst"],
    "preferred_locations": ["Berlin", "Remote"],
    "preferred_work_modes": ["remote", "hybrid"],
    "experience_level": "internship",
    "education_level": "bachelor",
    "education": [
        {
            "institution": "State University",
            "degree": "BSc",
            "field": "Computer Science",
            "start_year": 2021,
            "end_year": 2025,
        }
    ],
    "technical_skills": ["TypeScript", "ReactJS", "react", " React ", "postgres"],
    "soft_skills": ["Communication"],
    "projects": [
        {
            "name": "Job Tracker",
            "description": "Kanban for applications",
            "technologies": ["React", "FastAPI"],
            "url": "https://tracker.example.com",
        }
    ],
    "certifications": [{"name": "Cloud Practitioner", "issuer": "Cloud Co", "year": 2024}],
    "resume_text": "Built a React dashboard.",
    "github_url": "https://github.com/ada",
    "portfolio_url": "https://ada.example.com",
    "linkedin_url": "https://www.linkedin.com/in/ada",
}


def count(session: Session, model: type) -> int:
    return session.scalar(sa.select(sa.func.count()).select_from(model)) or 0


def test_get_profile_returns_every_field(client: TestClient, demo_user: User) -> None:
    response = client.get(PROFILE_PATH)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == PROFILE_FIELDS
    assert body["id"] == demo_user.id
    assert body["email"] == "demo@internpilot.dev"
    assert body["technical_skills"] == []
    assert body["resume_text"] == ""
    assert body["created_at"] == "2024-12-01T08:00:00Z"
    assert body["updated_at"] == "2024-12-01T08:00:00Z"
    assert "seed_key" not in body
    assert response.headers["X-Request-ID"]


def test_get_profile_without_demo_user_returns_503(client: TestClient) -> None:
    response = client.get(PROFILE_PATH)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DEMO_USER_NOT_SEEDED"


def test_put_profile_persists_and_returns_stored_profile(
    client: TestClient, demo_user: User
) -> None:
    response = client.put(PROFILE_PATH, json=FULL_PROFILE)

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Ada Student"
    assert body["email"] == "ada@example.org"
    assert body["target_roles"] == ["Frontend Engineer", "Data Analyst"]
    assert body["preferred_work_modes"] == ["remote", "hybrid"]
    assert body["experience_level"] == "internship"
    assert body["education"] == FULL_PROFILE["education"]
    assert body["projects"] == FULL_PROFILE["projects"]
    assert body["certifications"] == FULL_PROFILE["certifications"]
    assert body["linkedin_url"] == "https://www.linkedin.com/in/ada"
    assert client.get(PROFILE_PATH).json() == body


def test_put_profile_skills_deduped_by_alias_and_case(
    client: TestClient, demo_user: User, db_session: Session
) -> None:
    body = client.put(PROFILE_PATH, json=FULL_PROFILE).json()

    # Display names, sorted by normalized name: postgresql, react, typescript.
    assert body["technical_skills"] == ["PostgreSQL", "React", "TypeScript"]
    react_rows = db_session.scalars(sa.select(Skill).where(Skill.normalized_name == "react"))
    assert len(list(react_rows)) == 1
    assert count(db_session, UserSkill) == 3


def test_put_profile_reuses_existing_catalog_skill(
    client: TestClient, demo_user: User, db_session: Session
) -> None:
    db_session.add(Skill(name="React", normalized_name="react"))
    db_session.commit()

    client.put(PROFILE_PATH, json={**FULL_PROFILE, "technical_skills": ["react.js"]})

    assert count(db_session, Skill) == 1


def test_put_profile_full_replace_clears_omitted_fields(
    client: TestClient, demo_user: User
) -> None:
    client.put(PROFILE_PATH, json=FULL_PROFILE)

    body = client.put(PROFILE_PATH, json={"name": "Ada", "email": "ada@example.org"}).json()

    assert body["technical_skills"] == []
    assert body["projects"] == []
    assert body["github_url"] is None
    assert body["experience_level"] is None


def test_put_profile_sets_updated_at_from_clock(client: TestClient, demo_user: User) -> None:
    body = client.put(PROFILE_PATH, json=FULL_PROFILE).json()

    assert body["updated_at"] == "2025-01-15T09:30:00Z"
    assert body["created_at"] == "2024-12-01T08:00:00Z"


def test_put_profile_records_activity_event(
    client: TestClient, demo_user: User, db_session: Session
) -> None:
    client.put(PROFILE_PATH, json=FULL_PROFILE)

    events = list(db_session.scalars(sa.select(ActivityEvent)))
    assert [(event.type, event.user_id) for event in events] == [("profile_updated", demo_user.id)]
    assert events[0].created_at.isoformat() == "2025-01-15T09:30:00+00:00"


def test_put_profile_new_email_still_resolves_default_user(
    client: TestClient, demo_user: User
) -> None:
    client.put(PROFILE_PATH, json=FULL_PROFILE)

    response = client.get(PROFILE_PATH)

    assert response.status_code == 200
    assert response.json()["email"] == "ada@example.org"


@pytest.mark.parametrize(
    ("overrides", "loc"),
    [
        ({"github_url": "ftp://github.com/ada"}, ["body", "github_url"]),
        ({"github_url": "https://gitlab.com/ada"}, ["body", "github_url"]),
        ({"technical_skills": ["React", "(,)"]}, ["body", "technical_skills", 1]),
        ({"experience_level": "guru"}, ["body", "experience_level"]),
        ({"unknown_field": "sneaky-value"}, ["body", "unknown_field"]),
    ],
)
def test_put_profile_invalid_returns_422_and_persists_nothing(
    client: TestClient,
    demo_user: User,
    db_session: Session,
    overrides: dict[str, object],
    loc: list[object],
) -> None:
    response = client.put(PROFILE_PATH, json={**FULL_PROFILE, **overrides})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert loc in [detail["loc"] for detail in error["details"]]
    assert all(set(detail) == {"loc", "msg", "type"} for detail in error["details"])
    for value in overrides.values():
        if isinstance(value, str):
            assert value not in response.text
    assert response.headers["X-Request-ID"]
    profile = client.get(PROFILE_PATH).json()
    assert profile["name"] == "Demo Student"
    assert profile["technical_skills"] == []
    assert count(db_session, ActivityEvent) == 0
    assert count(db_session, Skill) == 0


def test_put_profile_email_taken_returns_409_and_persists_nothing(
    client: TestClient, demo_user: User, db_session: Session
) -> None:
    db_session.add(User(name="Other", email="ada@example.org"))
    db_session.commit()

    response = client.put(PROFILE_PATH, json=FULL_PROFILE)

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "EMAIL_TAKEN",
            "message": "This email is already used by another user.",
            "details": None,
        }
    }
    profile = client.get(PROFILE_PATH).json()
    assert profile["name"] == "Demo Student"
    assert profile["email"] == "demo@internpilot.dev"
    assert count(db_session, ActivityEvent) == 0
    assert count(db_session, Skill) == 0


def test_put_profile_keeping_own_email_succeeds(client: TestClient, demo_user: User) -> None:
    payload = {**FULL_PROFILE, "email": "DEMO@internpilot.dev"}

    response = client.put(PROFILE_PATH, json=payload)

    assert response.status_code == 200
    assert response.json()["email"] == "demo@internpilot.dev"
