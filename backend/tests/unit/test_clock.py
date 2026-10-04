"""Tests for the injectable Clock implementations."""

import dataclasses
from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from app.core.clock import Clock, FixedClock, SystemClock


def test_fixed_clock_now_returns_given_instant() -> None:
    instant = datetime(2026, 3, 10, 12, 30, tzinfo=UTC)

    assert FixedClock(instant).now() == instant


def test_fixed_clock_today_returns_utc_date() -> None:
    clock = FixedClock(datetime(2026, 3, 10, 23, 59, tzinfo=UTC))

    assert clock.today() == date(2026, 3, 10)


def test_fixed_clock_non_utc_offset_normalized_to_utc() -> None:
    ist = timezone(timedelta(hours=5, minutes=30))
    clock = FixedClock(datetime(2026, 3, 11, 2, 0, tzinfo=ist))

    assert clock.now().tzinfo is UTC
    assert clock.now() == datetime(2026, 3, 10, 20, 30, tzinfo=UTC)
    assert clock.today() == date(2026, 3, 10)


def test_fixed_clock_naive_datetime_raises() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        FixedClock(datetime(2026, 3, 10, 12, 0))


def test_fixed_clock_is_frozen() -> None:
    clock = FixedClock(datetime(2026, 3, 10, tzinfo=UTC))

    with pytest.raises(dataclasses.FrozenInstanceError):
        clock.instant = datetime(2027, 1, 1, tzinfo=UTC)  # type: ignore[misc]


def test_fixed_clock_repeated_calls_return_same_value() -> None:
    clock = FixedClock(datetime(2026, 3, 10, 8, 0, tzinfo=UTC))

    assert clock.now() == clock.now()


def test_system_clock_now_is_utc_aware() -> None:
    now = SystemClock().now()

    assert now.tzinfo is UTC


def test_system_clock_today_matches_utc_now_date() -> None:
    clock = SystemClock()

    before = datetime.now(UTC).date()
    today = clock.today()
    after = datetime.now(UTC).date()

    assert today in {before, after}


def test_clock_implementations_satisfy_protocol() -> None:
    clocks: list[Clock] = [SystemClock(), FixedClock(datetime(2026, 1, 1, tzinfo=UTC))]

    assert all(isinstance(clock.today(), date) for clock in clocks)
