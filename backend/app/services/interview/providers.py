"""Interview question providers (R9.4, R9.5, R15, design.md §10).

`TemplateInterviewProvider` is deterministic and the default. `LlmEnrichedInterviewProvider`
appends up to five extra technical questions from an OpenAI-compatible endpoint and falls back to
the template result on any failure. LLM output is untrusted text and never affects scores.
"""

import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

import httpx
from pydantic import SecretStr

from app.schemas.interview import (
    InterviewCategory,
    InterviewPrep,
    InterviewProviderName,
    InterviewQuestion,
    InterviewSection,
    PrepPriority,
    PrepTopic,
)
from app.services.interview.templates import (
    EMPLOYMENT_TYPE_LABELS,
    HR_QUESTIONS,
    PROJECT_FALLBACK_TEMPLATE,
    PROJECT_TEMPLATE,
    PROJECT_WITH_SKILLS_TEMPLATE,
    ROLE_TEMPLATES,
    SECTION_LIMITS,
    SECTION_TITLES,
    SKILL_TEMPLATE,
    TECHNICAL_GENERIC_TEMPLATES,
    TECHNICAL_SKILL_TEMPLATES,
    TOPIC_REASONS,
)
from app.services.matching.normalization import display_skill, normalize_skills
from app.services.matching.types import ProjectInput

logger = logging.getLogger(__name__)

LLM_TIMEOUT_SECONDS = 15.0
LLM_MAX_EXTRA_QUESTIONS = 5
LLM_MAX_QUESTION_LENGTH = 300
_PRIORITY_ORDER = {PrepPriority.HIGH: 0, PrepPriority.MEDIUM: 1, PrepPriority.LOW: 2}


@dataclass(frozen=True)
class InterviewContext:
    """Job and profile facts the providers may use; skills are canonical (normalized) names."""

    job_id: int
    title: str
    company: str
    employment_type: str
    required_skills: frozenset[str]
    preferred_skills: frozenset[str]
    profile_skills: frozenset[str]
    projects: tuple[ProjectInput, ...]


class InterviewQuestionProvider(Protocol):
    name: str

    def generate(self, ctx: InterviewContext) -> InterviewPrep: ...


def _questions(
    category: InterviewCategory, items: Sequence[tuple[str, str | None]]
) -> list[InterviewQuestion]:
    limited = items[: SECTION_LIMITS[category]]
    return [
        InterviewQuestion(id=f"{category}-{n}", category=category, text=text, skill=skill)
        for n, (text, skill) in enumerate(limited, start=1)
    ]


def _section(
    category: InterviewCategory, items: Sequence[tuple[str, str | None]]
) -> InterviewSection:
    return InterviewSection(
        category=category, title=SECTION_TITLES[category], questions=_questions(category, items)
    )


def _role_items(ctx: InterviewContext) -> list[tuple[str, str | None]]:
    employment = EMPLOYMENT_TYPE_LABELS.get(ctx.employment_type, ctx.employment_type)
    return [
        (template.format(title=ctx.title, company=ctx.company, employment_type=employment), None)
        for template in ROLE_TEMPLATES
    ]


def _technical_items(ctx: InterviewContext) -> list[tuple[str, str | None]]:
    skills = [*sorted(ctx.required_skills), *sorted(ctx.preferred_skills)]
    if not skills:
        return [
            (template.format(title=ctx.title), None) for template in TECHNICAL_GENERIC_TEMPLATES
        ]
    return [
        (template.format(skill=display_skill(skill)), display_skill(skill))
        for skill in skills
        for template in TECHNICAL_SKILL_TEMPLATES
    ]


def _skill_items(ctx: InterviewContext) -> list[tuple[str, str | None]]:
    skills = sorted(ctx.required_skills | ctx.preferred_skills)
    return [
        (SKILL_TEMPLATE.format(skill=display_skill(skill)), display_skill(skill))
        for skill in skills
    ]


def _project_items(ctx: InterviewContext) -> list[tuple[str, str | None]]:
    if not ctx.projects:
        return [(PROJECT_FALLBACK_TEMPLATE, None)]
    job_skills = ctx.required_skills | ctx.preferred_skills
    items: list[tuple[str, str | None]] = []
    for project in sorted(ctx.projects, key=lambda item: (item.name.casefold(), item.name)):
        used = sorted(normalize_skills(project.technologies) & job_skills)
        if used:
            skills = ", ".join(display_skill(skill) for skill in used)
            text = PROJECT_WITH_SKILLS_TEMPLATE.format(
                name=project.name, skills=skills, title=ctx.title
            )
        else:
            text = PROJECT_TEMPLATE.format(name=project.name)
        items.append((text, None))
    return items


def prep_topics(ctx: InterviewContext) -> list[PrepTopic]:
    """Missing required → high, matched required → medium, missing preferred → low (R9.3)."""
    ranked = [
        *((skill, PrepPriority.HIGH, "missing_required") for skill in
          ctx.required_skills - ctx.profile_skills),
        *((skill, PrepPriority.MEDIUM, "matched_required") for skill in
          ctx.required_skills & ctx.profile_skills),
        *((skill, PrepPriority.LOW, "missing_preferred") for skill in
          ctx.preferred_skills - ctx.profile_skills),
    ]  # fmt: skip
    ranked.sort(key=lambda item: (_PRIORITY_ORDER[item[1]], item[0]))
    return [
        PrepTopic(topic=display_skill(skill), reason=TOPIC_REASONS[reason], priority=priority)
        for skill, priority, reason in ranked
    ]


class TemplateInterviewProvider:
    """Deterministic templates; equal inputs give identical output (R9.6)."""

    name = InterviewProviderName.TEMPLATE.value

    def generate(self, ctx: InterviewContext) -> InterviewPrep:
        sections = [
            _section(InterviewCategory.ROLE, _role_items(ctx)),
            _section(InterviewCategory.TECHNICAL, _technical_items(ctx)),
            _section(InterviewCategory.SKILL, _skill_items(ctx)),
            _section(InterviewCategory.PROJECT, _project_items(ctx)),
            _section(InterviewCategory.HR, [(text, None) for text in HR_QUESTIONS]),
        ]
        return InterviewPrep(
            job_id=ctx.job_id,
            provider=InterviewProviderName.TEMPLATE,
            sections=[section for section in sections if section.questions],
            prep_topics=prep_topics(ctx),
        )


class LlmResponseError(Exception):
    """The LLM answered, but not with a usable JSON array of strings."""


def _parse_questions(payload: object) -> list[str]:
    """Valid questions from an OpenAI-compatible chat completion body."""
    try:
        content = payload["choices"][0]["message"]["content"]  # type: ignore[index]
    except (KeyError, IndexError, TypeError) as error:
        raise LlmResponseError from error
    if not isinstance(content, str):
        raise LlmResponseError
    try:
        items = json.loads(content)
    except ValueError as error:
        raise LlmResponseError from error
    if not isinstance(items, list):
        raise LlmResponseError
    questions = [
        item.strip()
        for item in items
        if isinstance(item, str) and item.strip() and len(item.strip()) <= LLM_MAX_QUESTION_LENGTH
    ]
    return questions[:LLM_MAX_EXTRA_QUESTIONS]


def _fallback_reason(error: Exception) -> str:
    if isinstance(error, httpx.TimeoutException):
        return "timeout"
    if isinstance(error, httpx.HTTPStatusError):
        return f"http_status_{error.response.status_code}"
    if isinstance(error, httpx.HTTPError):
        return "network_error"
    return "invalid_response"


class LlmEnrichedInterviewProvider:
    """Template result plus up to five LLM technical questions; template on any failure."""

    name = InterviewProviderName.LLM.value

    def __init__(
        self,
        *,
        base_url: str,
        api_key: SecretStr,
        model: str,
        transport: httpx.BaseTransport | None = None,
        template: TemplateInterviewProvider | None = None,
    ) -> None:
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._api_key = api_key
        self._model = model
        self._transport = transport
        self._template = template or TemplateInterviewProvider()

    def generate(self, ctx: InterviewContext) -> InterviewPrep:
        base = self._template.generate(ctx)
        try:
            extra = self._fetch_questions(ctx)
        except (httpx.HTTPError, LlmResponseError) as error:
            logger.warning("llm_fallback reason=%s", _fallback_reason(error))
            return base
        if not extra:
            return base
        return self._enrich(base, extra)

    def _prompt(self, ctx: InterviewContext) -> str:
        skills = ", ".join(
            display_skill(skill) for skill in sorted(ctx.required_skills | ctx.preferred_skills)
        )
        return (
            f"Job title: {ctx.title}\nCompany: {ctx.company}\nSkills: {skills or 'none listed'}\n"
            f"Write up to {LLM_MAX_EXTRA_QUESTIONS} additional technical interview questions "
            "for this job. Answer with only a JSON array of strings."
        )

    def _fetch_questions(self, ctx: InterviewContext) -> list[str]:
        body = {
            "model": self._model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": "You write concise technical interview questions."},
                {"role": "user", "content": self._prompt(ctx)},
            ],
        }
        headers = {"Authorization": f"Bearer {self._api_key.get_secret_value()}"}
        with httpx.Client(
            transport=self._transport, timeout=LLM_TIMEOUT_SECONDS, follow_redirects=False
        ) as client:
            response = client.post(self._url, json=body, headers=headers)
            response.raise_for_status()
            try:
                payload = response.json()
            except ValueError as error:
                raise LlmResponseError from error
        return _parse_questions(payload)

    @staticmethod
    def _enrich(base: InterviewPrep, extra: Sequence[str]) -> InterviewPrep:
        sections: list[InterviewSection] = []
        for section in base.sections:
            if section.category is InterviewCategory.TECHNICAL:
                start = len(section.questions) + 1
                added = [
                    InterviewQuestion(
                        id=f"{InterviewCategory.TECHNICAL}-{n}",
                        category=InterviewCategory.TECHNICAL,
                        text=text,
                        skill=None,
                    )
                    for n, text in enumerate(extra, start=start)
                ]
                section = section.model_copy(update={"questions": [*section.questions, *added]})
            sections.append(section)
        return base.model_copy(update={"provider": InterviewProviderName.LLM, "sections": sections})
