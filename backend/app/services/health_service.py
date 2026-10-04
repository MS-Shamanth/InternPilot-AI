"""Liveness/readiness probe behind `GET /api/health` (R12.6, design.md §14)."""

import logging

import sqlalchemy as sa
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.schemas.health import DatabaseStatus, HealthResponse, HealthStatus

logger = logging.getLogger(__name__)


class HealthService:
    """Reports `ok` when `SELECT 1` succeeds, else `degraded` with the database `unavailable`.

    `session` is `None` when no session could be obtained at all (see `get_health_session`).
    """

    def __init__(self, session: Session | None, version: str) -> None:
        self._session = session
        self._version = version

    def check(self) -> HealthResponse:
        if self._session is not None and self._database_reachable(self._session):
            return HealthResponse(
                status=HealthStatus.OK, database=DatabaseStatus.OK, version=self._version
            )
        return HealthResponse(
            status=HealthStatus.DEGRADED,
            database=DatabaseStatus.UNAVAILABLE,
            version=self._version,
        )

    @staticmethod
    def _database_reachable(session: Session) -> bool:
        try:
            session.execute(sa.select(1)).scalar_one()
        except SQLAlchemyError as exc:
            # Only the exception type: the message may contain SQL or the database URL.
            logger.warning("Health check database probe failed: %s", type(exc).__name__)
            return False
        return True
