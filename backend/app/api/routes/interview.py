"""`GET /api/interview/{job_id}` (R9, R15, design.md §8, §10)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path

from app.core.config import Settings, get_settings
from app.core.deps import CurrentUser, SessionDep
from app.schemas.interview import InterviewPrep
from app.services.interview.providers import InterviewQuestionProvider
from app.services.interview.service import InterviewService, build_interview_provider

router = APIRouter(prefix="/interview", tags=["interview"])


def get_interview_provider(
    settings: Annotated[Settings, Depends(get_settings)],
) -> InterviewQuestionProvider:
    """Template provider unless the LLM is enabled and configured; tests override this."""
    return build_interview_provider(settings)


def get_interview_service(
    session: SessionDep,
    provider: Annotated[InterviewQuestionProvider, Depends(get_interview_provider)],
) -> InterviewService:
    return InterviewService(session, provider)


InterviewServiceDep = Annotated[InterviewService, Depends(get_interview_service)]
JobId = Annotated[int, Path(ge=1)]


@router.get("/{job_id}")
def get_interview_prep(
    job_id: JobId, user: CurrentUser, service: InterviewServiceDep
) -> InterviewPrep:
    """Role, technical, skill, project and HR questions plus ranked prep topics."""
    return service.prepare(user, job_id)
