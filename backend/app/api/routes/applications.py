"""`/api/applications` tracker endpoints (R5, design.md §8)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status

from app.core.deps import ClockDep, CurrentUser, SessionDep
from app.schemas.application import (
    Application,
    ApplicationCreate,
    ApplicationsMeta,
    ApplicationUpdate,
)
from app.services.application_service import ApplicationService
from app.services.application_status import ApplicationStatus

router = APIRouter(prefix="/applications", tags=["applications"])


def get_application_service(session: SessionDep, clock: ClockDep) -> ApplicationService:
    return ApplicationService(session, clock)


ApplicationServiceDep = Annotated[ApplicationService, Depends(get_application_service)]
ApplicationId = Annotated[int, Path(ge=1)]
StatusFilter = Annotated[list[ApplicationStatus] | None, Query(alias="status")]


@router.get("")
def list_applications(
    user: CurrentUser, service: ApplicationServiceDep, statuses: StatusFilter = None
) -> list[Application]:
    """All of the user's applications (max 500), optionally filtered by repeated `status`."""
    return service.list_applications(user, statuses)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_application(
    payload: ApplicationCreate, user: CurrentUser, service: ApplicationServiceDep
) -> Application:
    """Track a job; 409 `DUPLICATE_APPLICATION` if it is already tracked."""
    return service.create(user, payload)


# Declared before the `/{application_id}` routes so `meta` is never parsed as an id.
@router.get("/meta")
def read_applications_meta(service: ApplicationServiceDep) -> ApplicationsMeta:
    """Statuses and allowed transitions, so the UI renders only allowed moves."""
    return service.meta()


@router.patch("/{application_id}")
def update_application(
    application_id: ApplicationId,
    payload: ApplicationUpdate,
    user: CurrentUser,
    service: ApplicationServiceDep,
) -> Application:
    """Partially update an application; status changes follow the transition table."""
    return service.update(user, application_id, payload)


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_application(
    application_id: ApplicationId, user: CurrentUser, service: ApplicationServiceDep
) -> None:
    """Delete an application."""
    service.delete(user, application_id)
