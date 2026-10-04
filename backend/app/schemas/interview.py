"""Interview prep API contract (R9, R15, design.md §8.3, §10)."""

from enum import StrEnum

from pydantic import BaseModel


class InterviewProviderName(StrEnum):
    TEMPLATE = "template"
    LLM = "llm"


class InterviewCategory(StrEnum):
    """Question sections in their output order."""

    ROLE = "role"
    TECHNICAL = "technical"
    SKILL = "skill"
    PROJECT = "project"
    HR = "hr"


class PrepPriority(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class InterviewQuestion(BaseModel):
    id: str
    category: InterviewCategory
    text: str
    skill: str | None


class InterviewSection(BaseModel):
    category: InterviewCategory
    title: str
    questions: list[InterviewQuestion]


class PrepTopic(BaseModel):
    topic: str
    reason: str
    priority: PrepPriority


class InterviewPrep(BaseModel):
    job_id: int
    provider: InterviewProviderName
    sections: list[InterviewSection]
    prep_topics: list[PrepTopic]
