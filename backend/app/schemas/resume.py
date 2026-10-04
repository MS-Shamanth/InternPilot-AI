"""Resume analysis API contract (R8, design.md §8.1, §8.3, §9)."""

from enum import StrEnum

from pydantic import BaseModel, Field

from app.schemas.common import RequestModel
from app.schemas.match import MatchExplanation

RESUME_TEXT_MAX_LENGTH = 50_000


class ResumeAnalyzeRequest(RequestModel):
    """`resume_text` omitted, null or blank → the profile's stored resume is analyzed."""

    job_id: int = Field(ge=1)
    resume_text: str | None = Field(default=None, max_length=RESUME_TEXT_MAX_LENGTH)


class ResumeSource(StrEnum):
    REQUEST = "request"
    PROFILE = "profile"


class ResumeSuggestionRule(StrEnum):
    """Suggestion rules in their output order (design.md §9.3)."""

    ADD_PROFILE_SKILL = "ADD_PROFILE_SKILL"
    GAP_REQUIRED_SKILL = "GAP_REQUIRED_SKILL"
    MENTION_PROJECT = "MENTION_PROJECT"
    ADD_KEYWORDS = "ADD_KEYWORDS"
    QUANTIFY = "QUANTIFY"
    LENGTH_SHORT = "LENGTH_SHORT"
    LENGTH_LONG = "LENGTH_LONG"
    ADD_LINKS = "ADD_LINKS"


class ResumeMatchingSkill(BaseModel):
    skill: str
    is_required: bool


class ResumeMissingSkill(BaseModel):
    skill: str
    is_required: bool
    in_profile: bool


class ResumeRelevantProject(BaseModel):
    name: str
    matched_skills: list[str]
    mentioned_in_resume: bool


class ResumeSuggestion(BaseModel):
    rule: ResumeSuggestionRule
    message: str
    evidence: list[str]


class ResumeAnalysis(BaseModel):
    """Resume-vs-job comparison; skills are display names (design.md §8.3)."""

    job_id: int
    resume_source: ResumeSource
    word_count: int
    compatibility_score: int
    matching_skills: list[ResumeMatchingSkill]
    missing_skills: list[ResumeMissingSkill]
    relevant_projects: list[ResumeRelevantProject]
    missing_keywords: list[str]
    suggestions: list[ResumeSuggestion]
    match_explanation: MatchExplanation
