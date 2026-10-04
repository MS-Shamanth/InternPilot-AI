"""`GET /api/dashboard` (R6, design.md §7, §8)."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.deps import ClockDep, CurrentUser, SessionDep
from app.schemas.dashboard import Dashboard
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def get_dashboard_service(session: SessionDep, clock: ClockDep) -> DashboardService:
    return DashboardService(session, clock)


DashboardServiceDep = Annotated[DashboardService, Depends(get_dashboard_service)]


@router.get("")
def read_dashboard(user: CurrentUser, service: DashboardServiceDep) -> Dashboard:
    """All dashboard metrics, computed fresh for the current user."""
    return service.get(user)
