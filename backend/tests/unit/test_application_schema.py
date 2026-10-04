"""Unit tests for application request schemas (R5.1, R5.7, design.md §8.1)."""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.schemas.application import ApplicationCreate, ApplicationUpdate

pytestmark = pytest.mark.unit


def test_application_create_naive_interview_date_is_assumed_utc() -> None:
    created = ApplicationCreate(job_id=1, interview_date=datetime(2025, 1, 20, 14, 0))
    assert created.interview_date == datetime(2025, 1, 20, 14, 0, tzinfo=UTC)


def test_application_update_aware_interview_date_is_converted_to_utc() -> None:
    plus_two = timezone(timedelta(hours=2))
    updated = ApplicationUpdate(interview_date=datetime(2025, 1, 20, 16, 0, tzinfo=plus_two))
    assert updated.interview_date == datetime(2025, 1, 20, 14, 0, tzinfo=UTC)
    assert updated.interview_date is not None
    assert updated.interview_date.tzinfo is UTC
