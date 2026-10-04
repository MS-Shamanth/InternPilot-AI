"""Unit tests for app.core.deps (design.md §3.2)."""

import pytest

from app.core.clock import SystemClock
from app.core.deps import get_clock

pytestmark = pytest.mark.unit


def test_get_clock_default_returns_system_clock() -> None:
    assert isinstance(get_clock(), SystemClock)
