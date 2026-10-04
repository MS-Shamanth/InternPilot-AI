"""Unit tests for interview templates, limits and the LLM provider fallback (R9, R15, §10)."""

import json
import logging

import httpx
import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.schemas.interview import InterviewCategory, InterviewPrep, PrepPriority
from app.services.interview.providers import (
    InterviewContext,
    LlmEnrichedInterviewProvider,
    TemplateInterviewProvider,
)
from app.services.interview.service import build_interview_provider
from app.services.matching.types import ProjectInput

pytestmark = pytest.mark.unit

MANY_SKILLS = frozenset({"python", "react", "sql", "docker", "aws", "git"})


def make_ctx(**overrides: object) -> InterviewContext:
    values: dict[str, object] = {
        "job_id": 7,
        "title": "Backend Intern",
        "company": "Example Co",
        "employment_type": "internship",
        "required_skills": frozenset({"python", "sql"}),
        "preferred_skills": frozenset({"docker"}),
        "profile_skills": frozenset({"python"}),
        "projects": (),
    }
    values.update(overrides)
    return InterviewContext(**values)  # type: ignore[arg-type]


def section(prep: InterviewPrep, category: InterviewCategory) -> list[str]:
    found = next(item for item in prep.sections if item.category is category)
    return [question.text for question in found.questions]


def test_template_sections_in_order_with_ids() -> None:
    prep = TemplateInterviewProvider().generate(make_ctx())
    assert prep.provider == "template"
    assert [item.category for item in prep.sections] == list(InterviewCategory)
    for item in prep.sections:
        assert [q.id for q in item.questions] == [
            f"{item.category}-{n}" for n in range(1, len(item.questions) + 1)
        ]


def test_template_limits_applied() -> None:
    projects = tuple(ProjectInput(name=f"P{i}", technologies=("Python",)) for i in range(5))
    ctx = make_ctx(
        required_skills=MANY_SKILLS,
        preferred_skills=frozenset({"figma", "jest", "vue"}),
        projects=projects,
    )
    prep = TemplateInterviewProvider().generate(ctx)
    counts = {item.category: len(item.questions) for item in prep.sections}
    assert counts == {
        InterviewCategory.ROLE: 5,
        InterviewCategory.TECHNICAL: 10,
        InterviewCategory.SKILL: 8,
        InterviewCategory.PROJECT: 3,
        InterviewCategory.HR: 5,
    }


def test_template_technical_required_alphabetical_then_preferred() -> None:
    prep = TemplateInterviewProvider().generate(make_ctx())
    technical = next(s for s in prep.sections if s.category is InterviewCategory.TECHNICAL)
    assert [q.skill for q in technical.questions] == [
        "Python",
        "Python",
        "SQL",
        "SQL",
        "Docker",
        "Docker",
    ]


def test_template_no_skills_uses_generic_technical_and_omits_skill_section() -> None:
    ctx = make_ctx(required_skills=frozenset(), preferred_skills=frozenset())
    prep = TemplateInterviewProvider().generate(ctx)
    assert InterviewCategory.SKILL not in [item.category for item in prep.sections]
    technical = section(prep, InterviewCategory.TECHNICAL)
    assert len(technical) == 3
    assert "Backend Intern" in technical[0]


def test_template_role_uses_title_company_and_employment_type() -> None:
    role = section(TemplateInterviewProvider().generate(make_ctx()), InterviewCategory.ROLE)
    assert role[0] == "Why do you want this Backend Intern position at Example Co?"
    assert "internship at Example Co" in role[2]


def test_template_projects_sorted_and_skill_aware_with_fallback() -> None:
    projects = (
        ProjectInput(name="zeta", technologies=("Figma",)),
        ProjectInput(name="Alpha", technologies=("Python", "postgres")),
    )
    questions = section(
        TemplateInterviewProvider().generate(make_ctx(projects=projects)), InterviewCategory.PROJECT
    )
    assert questions[0].startswith('In your project "Alpha", how did you use Python')
    assert questions[1].startswith('Walk me through your project "zeta"')
    fallback = section(TemplateInterviewProvider().generate(make_ctx()), InterviewCategory.PROJECT)
    assert len(fallback) == 1


def test_prep_topics_ranked_by_priority_then_name() -> None:
    prep = TemplateInterviewProvider().generate(make_ctx())
    assert [(t.topic, t.priority) for t in prep.prep_topics] == [
        ("SQL", PrepPriority.HIGH),
        ("Python", PrepPriority.MEDIUM),
        ("Docker", PrepPriority.LOW),
    ]


def test_template_is_deterministic() -> None:
    provider = TemplateInterviewProvider()
    assert provider.generate(make_ctx()) == provider.generate(make_ctx())


def llm(handler: httpx.MockTransport) -> LlmEnrichedInterviewProvider:
    return LlmEnrichedInterviewProvider(
        base_url="https://llm.example.com/v1",
        api_key=SecretStr("test-key"),
        model="test-model",
        transport=handler,
    )


def completion(content: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def test_llm_appends_valid_questions_with_continuing_ids() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        items = ["  Q one ", "", "x" * 301, 5, "Q two", "Q3", "Q4", "Q5", "Q6"]
        return completion(json.dumps(items))

    prep = llm(httpx.MockTransport(handler)).generate(make_ctx())
    technical = next(s for s in prep.sections if s.category is InterviewCategory.TECHNICAL)
    added = technical.questions[6:]
    assert prep.provider == "llm"
    assert [(q.id, q.text, q.skill) for q in added[:2]] == [
        ("technical-7", "Q one", None),
        ("technical-8", "Q two", None),
    ]
    assert len(added) == 5
    assert str(seen[0].url) == "https://llm.example.com/v1/chat/completions"
    assert seen[0].headers["Authorization"] == "Bearer test-key"


@pytest.mark.parametrize(
    ("handler", "reason"),
    [
        (lambda request: httpx.Response(500), "http_status_500"),
        (lambda request: completion("not json"), "invalid_response"),
        (lambda request: httpx.Response(200, json={"choices": []}), "invalid_response"),
        (lambda request: httpx.Response(200, text="<html>"), "invalid_response"),
    ],
)
def test_llm_failure_falls_back_to_template_with_warning(
    handler: object, reason: str, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        prep = llm(httpx.MockTransport(handler)).generate(make_ctx())  # type: ignore[arg-type]
    assert prep == TemplateInterviewProvider().generate(make_ctx())
    assert f"llm_fallback reason={reason}" in caplog.text
    assert "test-key" not in caplog.text


def test_llm_timeout_falls_back(caplog: pytest.LogCaptureFixture) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with caplog.at_level(logging.WARNING):
        prep = llm(httpx.MockTransport(handler)).generate(make_ctx())
    assert prep.provider == "template"
    assert "llm_fallback reason=timeout" in caplog.text


def test_llm_no_valid_questions_returns_template() -> None:
    prep = llm(httpx.MockTransport(lambda request: completion('["", "  "]'))).generate(make_ctx())
    assert prep == TemplateInterviewProvider().generate(make_ctx())


def settings(**values: object) -> Settings:
    return Settings(database_url=SecretStr("sqlite://"), **values)  # type: ignore[arg-type]


def test_build_provider_template_unless_enabled_and_configured() -> None:
    configured = {
        "llm_base_url": "https://llm.example.com/v1",
        "llm_model": "m",
        "llm_api_key": SecretStr("k"),
    }
    assert isinstance(build_interview_provider(settings()), TemplateInterviewProvider)
    assert isinstance(build_interview_provider(settings(**configured)), TemplateInterviewProvider)
    partial = {**configured, "llm_model": ""}
    assert isinstance(
        build_interview_provider(settings(llm_enabled=True, **partial)), TemplateInterviewProvider
    )
    assert isinstance(
        build_interview_provider(settings(llm_enabled=True, **configured)),
        LlmEnrichedInterviewProvider,
    )
