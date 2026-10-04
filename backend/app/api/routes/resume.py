"""`POST /api/resume/analyze` (R8, design.md §8, §9)."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.deps import CurrentUser, SessionDep
from app.schemas.resume import ResumeAnalysis, ResumeAnalyzeRequest
from app.services.resume_service import ResumeService

router = APIRouter(prefix="/resume", tags=["resume"])


def get_resume_service(session: SessionDep) -> ResumeService:
    return ResumeService(session)


ResumeServiceDep = Annotated[ResumeService, Depends(get_resume_service)]


@router.post("/analyze")
def analyze_resume(
    body: ResumeAnalyzeRequest, user: CurrentUser, service: ResumeServiceDep
) -> ResumeAnalysis:
    """Compare the supplied (or stored) resume text with one job; nothing is persisted."""
    return service.analyze(user, body.job_id, body.resume_text)
