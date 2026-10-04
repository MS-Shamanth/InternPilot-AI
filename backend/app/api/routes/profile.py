"""`GET/PUT /api/profile` (R1, design.md §8)."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.deps import ClockDep, CurrentUser, SessionDep
from app.schemas.profile import Profile, ProfileUpdate
from app.services.profile_service import ProfileService

router = APIRouter(prefix="/profile", tags=["profile"])


def get_profile_service(session: SessionDep, clock: ClockDep) -> ProfileService:
    return ProfileService(session, clock)


ProfileServiceDep = Annotated[ProfileService, Depends(get_profile_service)]


@router.get("")
def read_profile(user: CurrentUser, service: ProfileServiceDep) -> Profile:
    """The current user's profile."""
    return service.get(user)


@router.put("")
def replace_profile(
    payload: ProfileUpdate, user: CurrentUser, service: ProfileServiceDep
) -> Profile:
    """Replace the whole profile; omitted optional fields are cleared."""
    return service.update(user, payload)
