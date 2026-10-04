"""Profile reads and full-replace updates (R1, design.md §4.1, §8.1)."""

import logging

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.errors import EmailTakenError
from app.models import User
from app.repositories.activity_repository import ActivityRepository
from app.repositories.skill_repository import SkillRepository
from app.repositories.user_repository import UserRepository
from app.schemas.profile import Profile, ProfileUpdate
from app.services.matching.normalization import display_skill, normalize_skills

logger = logging.getLogger(__name__)

PROFILE_UPDATED_EVENT = "profile_updated"
PROFILE_UPDATED_MESSAGE = "Profile updated"


class ProfileService:
    """Owns the profile unit of work: one commit per update, rollback on any failure (R1.4)."""

    def __init__(self, session: Session, clock: Clock) -> None:
        self._session = session
        self._clock = clock
        self._users = UserRepository(session)
        self._skills = SkillRepository(session)
        self._activity = ActivityRepository(session)

    def get(self, user: User) -> Profile:
        """The user's stored profile (R1.1)."""
        return self._to_profile(user)

    def update(self, user: User, data: ProfileUpdate) -> Profile:
        """Replace every profile field with `data` and record a `profile_updated` event.

        Raises `EmailTakenError` when another user already owns `data.email`. Nothing is
        persisted if any step fails.
        """
        try:
            self._ensure_email_available(user, data.email)
            self.apply(user, data)
            now = self._clock.now()
            user.updated_at = now
            self._activity.add(
                user.id, PROFILE_UPDATED_EVENT, PROFILE_UPDATED_MESSAGE, created_at=now
            )
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        logger.info("Profile updated for user_id=%d", user.id)
        return self._to_profile(user)

    def _ensure_email_available(self, user: User, email: str) -> None:
        owner = self._users.get_by_email(email)
        if owner is not None and owner.id != user.id:
            raise EmailTakenError

    def apply(self, user: User, data: ProfileUpdate) -> None:
        """Stage every field of `data` on `user`, technical skills included, without committing.

        The caller owns the unit of work: `update` (API) and the seed (`SeedService`) both use it.
        `user` must already be flushed so it has an id.
        """
        self._apply_fields(user, data)
        self._replace_technical_skills(user, data.technical_skills)

    @staticmethod
    def _apply_fields(user: User, data: ProfileUpdate) -> None:
        user.name = data.name
        user.email = data.email
        user.location = data.location
        user.target_roles = list(data.target_roles)
        user.preferred_locations = list(data.preferred_locations)
        user.preferred_work_modes = [mode.value for mode in data.preferred_work_modes]
        user.experience_level = data.experience_level.value if data.experience_level else None
        user.education_level = data.education_level.value if data.education_level else None
        user.education = [entry.model_dump(mode="json") for entry in data.education]
        user.soft_skills = list(data.soft_skills)
        user.projects = [project.model_dump(mode="json") for project in data.projects]
        user.certifications = [cert.model_dump(mode="json") for cert in data.certifications]
        user.resume_text = data.resume_text
        user.github_url = data.github_url
        user.portfolio_url = data.portfolio_url
        user.linkedin_url = data.linkedin_url

    def _replace_technical_skills(self, user: User, raw_skills: list[str]) -> None:
        """Store each skill once per normalized name, linked to the shared catalog (R1.3).

        New catalog rows take `display_skill(normalized)`, so the display name never depends
        on which spelling or order the user submitted.
        """
        display_by_normalized = {
            normalized: display_skill(normalized) for normalized in normalize_skills(raw_skills)
        }
        skills = self._skills.get_or_create_many(display_by_normalized)
        self._users.replace_skills(user, (skill.id for skill in skills.values()))

    def _to_profile(self, user: User) -> Profile:
        skills = self._users.list_skills(user.id)
        return Profile.model_validate(
            {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "location": user.location,
                "target_roles": user.target_roles,
                "preferred_locations": user.preferred_locations,
                "preferred_work_modes": user.preferred_work_modes,
                "experience_level": user.experience_level,
                "education_level": user.education_level,
                "education": user.education,
                "technical_skills": [skill.name for skill in skills],
                "soft_skills": user.soft_skills,
                "projects": user.projects,
                "certifications": user.certifications,
                "resume_text": user.resume_text,
                "github_url": user.github_url,
                "portfolio_url": user.portfolio_url,
                "linkedin_url": user.linkedin_url,
                "created_at": user.created_at,
                "updated_at": user.updated_at,
            }
        )
