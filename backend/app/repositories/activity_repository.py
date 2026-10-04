"""Queries for `activity_events` (design.md §4.1, §7 `recent_activity`)."""

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.models import ActivityEvent

RECENT_ACTIVITY_LIMIT = 10


class ActivityRepository:
    """Append and read a user's activity events; never commits."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self,
        user_id: int,
        event_type: str,
        message: str,
        job_id: int | None = None,
        application_id: int | None = None,
        created_at: datetime | None = None,
    ) -> ActivityEvent:
        """Stage an event. Pass `created_at` from the injected clock; else the DB default."""
        event = ActivityEvent(
            user_id=user_id,
            type=event_type,
            message=message,
            job_id=job_id,
            application_id=application_id,
        )
        if created_at is not None:
            event.created_at = created_at
        self._session.add(event)
        self._session.flush()
        return event

    def recent(self, user_id: int, limit: int = RECENT_ACTIVITY_LIMIT) -> list[ActivityEvent]:
        """The user's latest events, `created_at` desc then id desc."""
        statement = (
            sa.select(ActivityEvent)
            .where(ActivityEvent.user_id == user_id)
            .order_by(ActivityEvent.created_at.desc(), ActivityEvent.id.desc())
            .limit(limit)
        )
        return list(self._session.scalars(statement).all())
