"""Resume analysis against one job (R8, design.md §9). Read-only: nothing is persisted (R8.6)."""

from dataclasses import replace

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ResumeEmptyError
from app.models import Job, User
from app.repositories.job_repository import JobRepository
from app.repositories.skill_repository import SkillRepository
from app.schemas.match import match_explanation_from_result
from app.schemas.resume import (
    ResumeAnalysis,
    ResumeMatchingSkill,
    ResumeMissingSkill,
    ResumeRelevantProject,
    ResumeSource,
)
from app.services.application_service import JOB_NOT_FOUND_MESSAGE
from app.services.matching.engine import compute_match
from app.services.matching.normalization import display_skill, normalize_skills
from app.services.matching.skill_catalog import CATALOG
from app.services.matching.types import MatchProfile
from app.services.matching_inputs import match_job_from_job, match_profile_from_user
from app.services.resume_analysis import (
    ResumeText,
    build_suggestions,
    extract_resume_skills,
    missing_keywords,
    resume_views,
    word_count,
)


def select_resume_text(user: User, resume_text: str | None) -> tuple[str, ResumeSource]:
    """Request text unless blank, else the stored resume; both blank → `ResumeEmptyError`."""
    if resume_text is not None and resume_text.strip():
        return resume_text, ResumeSource.REQUEST
    if user.resume_text.strip():
        return user.resume_text, ResumeSource.PROFILE
    raise ResumeEmptyError


def _relevant_projects(
    profile: MatchProfile, job_skills: frozenset[str], resume: ResumeText
) -> list[ResumeRelevantProject]:
    projects = sorted(profile.projects, key=lambda project: (project.name.casefold(), project.name))
    relevant: list[ResumeRelevantProject] = []
    for project in projects:
        matched = normalize_skills(project.technologies) & job_skills
        if matched:
            relevant.append(
                ResumeRelevantProject(
                    name=project.name,
                    matched_skills=[display_skill(skill) for skill in sorted(matched)],
                    mentioned_in_resume=resume_views(project.name).folded in resume.folded,
                )
            )
    return relevant


class ResumeService:
    """Compare resume text with a job using the shared matching engine (R8.4, R3.12)."""

    def __init__(self, session: Session) -> None:
        self._jobs = JobRepository(session)
        self._skills = SkillRepository(session)

    def analyze(self, user: User, job_id: int, resume_text: str | None) -> ResumeAnalysis:
        job = self._require_job(job_id)
        text, source = select_resume_text(user, resume_text)
        resume = resume_views(text)
        match_job = match_job_from_job(job)
        required = normalize_skills(match_job.required_skills)
        preferred = normalize_skills(match_job.preferred_skills) - required
        job_skills = required | preferred
        catalog = (
            frozenset(CATALOG)
            | {skill.normalized_name for skill in self._skills.list_all()}
            | job_skills
        )
        resume_skills = extract_resume_skills(resume, catalog)
        profile = match_profile_from_user(user)
        profile_skills = normalize_skills(profile.technical_skills)
        result = compute_match(
            replace(profile, technical_skills=tuple(sorted(resume_skills))), match_job
        )
        missing = [
            ResumeMissingSkill(
                skill=display_skill(skill),
                is_required=skill in required,
                in_profile=skill in profile_skills,
            )
            for skill in sorted(job_skills - resume_skills)
        ]
        projects = _relevant_projects(profile, job_skills, resume)
        keywords = missing_keywords(job.description, resume, catalog)
        links = {
            label: url
            for label, url in (("GitHub", user.github_url), ("portfolio", user.portfolio_url))
            if url
        }
        return ResumeAnalysis(
            job_id=job.id,
            resume_source=source,
            word_count=word_count(resume),
            compatibility_score=result.score,
            matching_skills=[
                ResumeMatchingSkill(skill=display_skill(skill), is_required=skill in required)
                for skill in sorted(job_skills & resume_skills)
            ],
            missing_skills=missing,
            relevant_projects=projects,
            missing_keywords=keywords,
            suggestions=build_suggestions(
                missing=missing, projects=projects, keywords=keywords, resume=resume, links=links
            ),
            match_explanation=match_explanation_from_result(result),
        )

    def _require_job(self, job_id: int) -> Job:
        job = self._jobs.get_by_id(job_id)
        if job is None:
            raise NotFoundError(JOB_NOT_FOUND_MESSAGE)
        return job
