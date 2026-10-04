"""Mapping ORM users/jobs to engine inputs (design.md §3.3, R3.12); transient objects, no DB."""

from app.models import Job, JobSkill, Skill, User, UserSkill
from app.services.matching.types import (
    EducationLevel,
    ExperienceLevel,
    MatchJob,
    MatchProfile,
    ProjectInput,
    WorkMode,
)
from app.services.matching_inputs import match_job_from_job, match_profile_from_user

PYTHON = Skill(name="Python", normalized_name="python")
DOCKER = Skill(name="Docker", normalized_name="docker")


def test_match_profile_from_user_maps_every_field() -> None:
    user = User(
        name="Demo",
        email="demo@internpilot.dev",
        location="Berlin",
        experience_level="junior",
        education_level="bachelor",
        target_roles=["Backend Intern"],
        preferred_locations=["Munich"],
        preferred_work_modes=["remote", "hybrid"],
        projects=[{"name": "API", "description": "", "technologies": ["Python"], "url": None}],
        user_skills=[UserSkill(skill=PYTHON)],
    )

    assert match_profile_from_user(user) == MatchProfile(
        technical_skills=("Python",),
        target_roles=("Backend Intern",),
        location="Berlin",
        preferred_locations=("Munich",),
        preferred_work_modes=(WorkMode.REMOTE, WorkMode.HYBRID),
        experience_level=ExperienceLevel.JUNIOR,
        education_level=EducationLevel.BACHELOR,
        projects=(ProjectInput(name="API", technologies=("Python",)),),
    )


def test_match_profile_from_user_with_empty_profile_is_default() -> None:
    user = User(
        name="Demo",
        email="demo@internpilot.dev",
        target_roles=[],
        preferred_locations=[],
        preferred_work_modes=[],
        projects=[],
    )

    assert match_profile_from_user(user) == MatchProfile()


def test_match_job_from_job_splits_required_and_preferred_skills() -> None:
    job = Job(
        id=7,
        title="Backend Intern",
        location="Berlin, Germany",
        work_mode="onsite",
        experience_level=None,
        min_education_level="master",
        job_skills=[
            JobSkill(skill=PYTHON, is_required=True),
            JobSkill(skill=DOCKER, is_required=False),
        ],
    )

    assert match_job_from_job(job) == MatchJob(
        id=7,
        title="Backend Intern",
        location="Berlin, Germany",
        work_mode=WorkMode.ONSITE,
        min_education_level=EducationLevel.MASTER,
        required_skills=("Python",),
        preferred_skills=("Docker",),
    )
