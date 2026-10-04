"""`GET /api/health` (R12.6, design.md §8): 200 when the database answers, else 503.

Both responses carry the health body, never the error envelope (R12.2). No current-user
dependency: the probe must work before the demo user is seeded.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_health_session
from app.core.version import APP_VERSION
from app.schemas.health import HealthResponse, HealthStatus
from app.services.health_service import HealthService

router = APIRouter(prefix="/health", tags=["health"])


def get_health_service(
    session: Annotated[Session | None, Depends(get_health_session)],
) -> HealthService:
    return HealthService(session, APP_VERSION)


HealthServiceDep = Annotated[HealthService, Depends(get_health_service)]


@router.get(
    "",
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthResponse}},
)
def read_health(response: Response, service: HealthServiceDep) -> HealthResponse:
    """Database probe; 503 with `status="degraded"` when the database is unreachable."""
    health = service.check()
    if health.status is not HealthStatus.OK:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return health
