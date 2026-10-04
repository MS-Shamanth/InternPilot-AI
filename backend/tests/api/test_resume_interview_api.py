"""API tests for `POST /api/resume/analyze` (R8) and `GET /api/interview/{job_id}` (R9, R15)."""

import json
from collections.abc import Callable

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.orm import Session

from app.api.routes.interview import get_interview_provider
from app.models import Job, User, UserSkill
from app.repositories.job_repository import JobRepository
from app.repositories.skill_repository import SkillRepository
from app.services.interview.providers import (
    InterviewQuestionProvider,
    LlmEnrichedInterviewProvider,
)

pytestmark = pytest.mark.api

RESUME = "Built REST APIs in Python for 3 teams, cut costs 20% over 12 months. See Tracker."


@pytest.fixture
def job(db_session: Session, make_job: Callable[..., Job], demo_user: User) -> Job:
    """Requires Python + SQL, prefers Docker; the profile lists SQL and a Python project."""
    repo = SkillRepository(db_session)
    found = repo.get_or_create_many({"python": "Python", "sql": "SQL", "docker": "Docker"})
    job = make_job(
        "1", title="Backend Intern", description="Kafka pipelines and Kafka streams in Python."
    )
    JobRepository(db_session).replace_skills(
        job, required=[found["python"].id, found["sql"].id], preferred=[found["docker"].id]
    )
    demo_user.user_skills.append(UserSkill(skill_id=found["sql"].id))
    demo_user.projects = [{"name": "Tracker", "technologies": ["Python"]}]
    demo_user.github_url = "https://github.com/demo"
    db_session.commit()
    return job


def test_analyze_request_text_returns_full_analysis(client: TestClient, job: Job) -> None:
    response = client.post("/api/resume/analyze", json={"job_id": job.id, "resume_text": RESUME})
    assert response.status_code == 200
    body = response.json()
    assert body["resume_source"] == "request"
    assert body["matching_skills"] == [{"skill": "Python", "is_required": True}]
    assert body["missing_skills"] == [
        {"skill": "Docker", "is_required": False, "in_profile": False},
        {"skill": "SQL", "is_required": True, "in_profile": True},
    ]
    assert body["relevant_projects"] == [
        {"name": "Tracker", "matched_skills": ["Python"], "mentioned_in_resume": True}
    ]
    assert body["missing_keywords"] == ["kafka"]
    assert [item["rule"] for item in body["suggestions"]] == [
        "ADD_PROFILE_SKILL",
        "LENGTH_SHORT",
        "ADD_LINKS",
    ]
    assert body["compatibility_score"] == body["match_explanation"]["score"]
    assert body["match_explanation"]["matched_required_skills"] == ["Python"]


def test_analyze_blank_text_uses_profile_and_never_modifies_it(
    client: TestClient, db_session: Session, demo_user: User, job: Job
) -> None:
    demo_user.resume_text = "SQL and Docker"
    db_session.commit()
    first = client.post("/api/resume/analyze", json={"job_id": job.id, "resume_text": "   "})
    second = client.post("/api/resume/analyze", json={"job_id": job.id})
    assert first.status_code == 200
    assert first.json()["resume_source"] == "profile"
    assert first.json() == second.json()
    db_session.refresh(demo_user)
    assert demo_user.resume_text == "SQL and Docker"


def test_analyze_whitespace_with_empty_profile_returns_resume_empty(
    client: TestClient, job: Job
) -> None:
    response = client.post("/api/resume/analyze", json={"job_id": job.id, "resume_text": " \n\t"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "RESUME_EMPTY"


@pytest.mark.parametrize(
    "body",
    [{"job_id": 0}, {"job_id": 1, "resume_text": "x" * 50_001}, {"job_id": 1, "extra": 1}],
)
def test_analyze_invalid_body_returns_422(client: TestClient, job: Job, body: object) -> None:
    response = client.post("/api/resume/analyze", json=body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_analyze_unknown_job_returns_404(client: TestClient, demo_user: User) -> None:
    response = client.post("/api/resume/analyze", json={"job_id": 999, "resume_text": RESUME})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_interview_returns_template_prep(client: TestClient, job: Job) -> None:
    response = client.get(f"/api/interview/{job.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["job_id"] == job.id
    assert body["provider"] == "template"
    assert [s["category"] for s in body["sections"]] == [
        "role",
        "technical",
        "skill",
        "project",
        "hr",
    ]
    assert [(t["topic"], t["priority"]) for t in body["prep_topics"]] == [
        ("Python", "high"),
        ("SQL", "medium"),
        ("Docker", "low"),
    ]
    assert client.get(f"/api/interview/{job.id}").json() == body


def test_interview_unknown_job_returns_404(client: TestClient, demo_user: User) -> None:
    response = client.get("/api/interview/999")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def override_provider(app: FastAPI, handler: Callable[[httpx.Request], httpx.Response]) -> None:
    provider = LlmEnrichedInterviewProvider(
        base_url="https://llm.example.com/v1",
        api_key=SecretStr("test-key"),
        model="test-model",
        transport=httpx.MockTransport(handler),
    )

    def get_provider() -> InterviewQuestionProvider:
        return provider

    app.dependency_overrides[get_interview_provider] = get_provider


def test_interview_llm_enriches_technical_section(
    app: FastAPI, client: TestClient, job: Job
) -> None:
    content = json.dumps(["How would you shard this?"])
    override_provider(
        app,
        lambda request: httpx.Response(200, json={"choices": [{"message": {"content": content}}]}),
    )
    body = client.get(f"/api/interview/{job.id}").json()
    technical = next(s for s in body["sections"] if s["category"] == "technical")
    assert body["provider"] == "llm"
    assert technical["questions"][-1] == {
        "id": "technical-7",
        "category": "technical",
        "text": "How would you shard this?",
        "skill": None,
    }


def test_interview_llm_failure_falls_back_to_template(
    app: FastAPI, client: TestClient, job: Job
) -> None:
    template = client.get(f"/api/interview/{job.id}").json()
    override_provider(app, lambda request: httpx.Response(503))
    body = client.get(f"/api/interview/{job.id}").json()
    assert body == template
