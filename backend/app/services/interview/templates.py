"""Deterministic interview question templates and section limits (design.md §10, R9.2)."""

from collections.abc import Mapping
from types import MappingProxyType

from app.schemas.interview import InterviewCategory

SECTION_LIMITS: Mapping[InterviewCategory, int] = MappingProxyType(
    {
        InterviewCategory.ROLE: 5,
        InterviewCategory.TECHNICAL: 10,
        InterviewCategory.SKILL: 8,
        InterviewCategory.PROJECT: 3,
        InterviewCategory.HR: 5,
    }
)

SECTION_TITLES: Mapping[InterviewCategory, str] = MappingProxyType(
    {
        InterviewCategory.ROLE: "Role-specific questions",
        InterviewCategory.TECHNICAL: "Technical questions",
        InterviewCategory.SKILL: "Required skill questions",
        InterviewCategory.PROJECT: "Project questions",
        InterviewCategory.HR: "HR and behavioral questions",
    }
)

EMPLOYMENT_TYPE_LABELS: Mapping[str, str] = MappingProxyType(
    {
        "internship": "internship",
        "full_time": "full-time role",
        "part_time": "part-time role",
        "contract": "contract role",
    }
)

# Placeholders: {title}, {company}, {employment_type}. Only the first five are used.
ROLE_TEMPLATES: tuple[str, ...] = (
    "Why do you want this {title} position at {company}?",
    "What do you know about {company} and its products?",
    "What would you hope to learn during this {employment_type} at {company}?",
    "Which part of the {title} role excites you most, and why?",
    "How do your skills and projects prepare you for the {title} role?",
    "Where do you see yourself one year after this {employment_type}?",
)

# Placeholder: {skill} (display name). Two per job skill.
TECHNICAL_SKILL_TEMPLATES: tuple[str, ...] = (
    "Explain the core concepts of {skill} and when you would choose it.",
    "Walk through how you would debug a problem in a {skill} codebase.",
)

# Used when the job lists no skills. Placeholder: {title}.
TECHNICAL_GENERIC_TEMPLATES: tuple[str, ...] = (
    "What core technical concepts should a {title} understand well?",
    "Describe a recent technical problem you solved and how you approached it.",
    "How would you ramp up on the codebase and tools in your first month as a {title}?",
)

SKILL_TEMPLATE = "Describe a time you used {skill}: what was the goal and what was the outcome?"

PROJECT_WITH_SKILLS_TEMPLATE = (
    'In your project "{name}", how did you use {skills}, and what would you change for '
    "the {title} role?"
)
PROJECT_TEMPLATE = (
    'Walk me through your project "{name}": what problem did it solve and what was your part?'
)
PROJECT_FALLBACK_TEMPLATE = (
    "Tell me about a project you are proud of and the technical decisions you made."
)

HR_QUESTIONS: tuple[str, ...] = (
    "Tell me about yourself.",
    "Describe a time you disagreed with a teammate and how you resolved it.",
    "Tell me about a mistake you made and what you learned from it.",
    "How do you prioritize when you have several deadlines at once?",
    "What questions do you have for us?",
)

TOPIC_REASONS: Mapping[str, str] = MappingProxyType(
    {
        "missing_required": "Required skill not in your profile; learn the fundamentals.",
        "matched_required": "Required skill in your profile; be ready to go deep.",
        "missing_preferred": "Preferred skill not in your profile; a basic overview helps.",
    }
)
