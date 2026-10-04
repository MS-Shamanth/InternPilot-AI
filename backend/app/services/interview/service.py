"""Interview prep for one job (R9, R15, design.md §10)."""

import httpx
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import NotFoundError
from app.models import User
from app.repositories.job_repository import JobRepository
from app.schemas.interview import InterviewPrep
from app.services.application_service import JOB_NOT_FOUND_MESSAGE
from app.services.interview.providers import (
    InterviewContext,
    InterviewQuestionProvider,
    LlmEnrichedInterviewProvider,
    TemplateInterviewProvider,
)
from app.services.matching.normalization import normalize_skills
from app.services.matching_inputs import match_job_from_job, match_profile_from_user


def build_interview_provider(
    settings: Settings, transport: httpx.BaseTransport | None = None
) -> InterviewQuestionProvider:
    """The LLM provider only when enabled and fully configured (R15.1); templates otherwise."""
    configured = all(
        (settings.llm_base_url, settings.llm_model, settings.llm_api_key.get_secret_value())
    )
    if settings.llm_enabled and configured:
        return LlmEnrichedInterviewProvider(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            transport=transport,
        )
    return TemplateInterviewProvider()


class InterviewService:
    """Build the provider context from the live profile and job, then delegate (R9.4)."""

    def __init__(self, session: Session, provider: InterviewQuestionProvider) -> None:
        self._jobs = JobRepository(session)
        self._provider = provider

    def prepare(self, user: User, job_id: int) -> InterviewPrep:
        job = self._jobs.get_by_id(job_id)
        if job is None:
            raise NotFoundError(JOB_NOT_FOUND_MESSAGE)
        match_job = match_job_from_job(job)
        profile = match_profile_from_user(user)
        required = normalize_skills(match_job.required_skills)
        ctx = InterviewContext(
            job_id=job.id,
            title=job.title,
            company=job.company,
            employment_type=job.employment_type,
            required_skills=required,
            preferred_skills=normalize_skills(match_job.preferred_skills) - required,
            profile_skills=normalize_skills(profile.technical_skills),
            projects=profile.projects,
        )
        return self._provider.generate(ctx)
