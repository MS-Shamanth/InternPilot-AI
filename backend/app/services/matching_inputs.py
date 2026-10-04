"""Map ORM users and jobs to matching-engine inputs (design.md §3.3, §5).

The engine stays pure; this service-layer module is the one place that turns `User`/`Job` rows
into `MatchProfile`/`MatchJob`, so every caller scores the same way (R3.12).
"""

from collections.abc import Mapping

from app.models import Job, User
from app.services.matching.types import (
    EducationLevel,
    ExperienceLevel,
    MatchJob,
    MatchProfile,
    ProjectInput,
    WorkMode,
)


def _project_input(project: Mapping[str, object]) -> ProjectInput:
    """A stored profile project (`Project.model_dump(mode="json")`) as engine input."""
    technologies = project.get("technologies")
    return ProjectInput(
        name=str(project.get("name", "")),
        technologies=(
            tuple(str(tech) for tech in technologies) if isinstance(technologies, list) else ()
        ),
    )


def match_profile_from_user(user: User) -> MatchProfile:
    """The user's live profile as a `MatchProfile` (R1.6)."""
    return MatchProfile(
        technical_skills=tuple(link.skill.name for link in user.user_skills),
        target_roles=tuple(str(role) for role in user.target_roles),
        location=user.location,
        preferred_locations=tuple(str(location) for location in user.preferred_locations),
        preferred_work_modes=tuple(WorkMode(mode) for mode in user.preferred_work_modes),
        experience_level=(
            None if user.experience_level is None else ExperienceLevel(user.experience_level)
        ),
        education_level=(
            None if user.education_level is None else EducationLevel(user.education_level)
        ),
        projects=tuple(
            _project_input(project) for project in user.projects if isinstance(project, Mapping)
        ),
    )


def match_job_from_job(job: Job) -> MatchJob:
    """A stored job as a `MatchJob`; skills are display names, the engine normalizes them."""
    return MatchJob(
        id=job.id,
        title=job.title,
        location=job.location,
        work_mode=WorkMode(job.work_mode),
        experience_level=(
            None if job.experience_level is None else ExperienceLevel(job.experience_level)
        ),
        min_education_level=(
            None if job.min_education_level is None else EducationLevel(job.min_education_level)
        ),
        required_skills=tuple(link.skill.name for link in job.job_skills if link.is_required),
        preferred_skills=tuple(link.skill.name for link in job.job_skills if not link.is_required),
    )
