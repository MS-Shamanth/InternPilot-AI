"""Unit tests for `activity_message` (activity_events.message is varchar 300, design.md §4)."""

import pytest

from app.services.application_service import ACTIVITY_MESSAGE_MAX_LENGTH, activity_message

pytestmark = pytest.mark.unit


def test_activity_message_within_limit_is_unchanged() -> None:
    text = "x" * ACTIVITY_MESSAGE_MAX_LENGTH
    assert activity_message(text) == text


def test_activity_message_over_limit_is_truncated_with_ellipsis() -> None:
    message = activity_message("x" * (ACTIVITY_MESSAGE_MAX_LENGTH + 50))
    assert len(message) == ACTIVITY_MESSAGE_MAX_LENGTH
    assert message.endswith("…")
