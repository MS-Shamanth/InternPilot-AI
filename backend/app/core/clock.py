"""Injectable time source (design.md §3.2).

Code under test never calls `datetime.now()` / `date.today()` directly; it receives a `Clock`.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Protocol


class Clock(Protocol):
    """Source of the current UTC time."""

    def now(self) -> datetime:
        """Return the current time as a timezone-aware UTC datetime."""
        ...

    def today(self) -> date:
        """Return the current UTC calendar date."""
        ...


class SystemClock:
    """Clock backed by the system time."""

    def now(self) -> datetime:
        return datetime.now(UTC)

    def today(self) -> date:
        return self.now().date()


@dataclass(frozen=True)
class FixedClock:
    """Clock that always returns the same instant; used by tests for deterministic time."""

    instant: datetime

    def __post_init__(self) -> None:
        if self.instant.tzinfo is None or self.instant.utcoffset() is None:
            raise ValueError("FixedClock requires a timezone-aware datetime")
        object.__setattr__(self, "instant", self.instant.astimezone(UTC))

    def now(self) -> datetime:
        return self.instant

    def today(self) -> date:
        return self.instant.date()
