"""Tests for logging setup and request-id injection (design.md §14)."""

import logging
from collections.abc import Iterator

import pytest

from app.core.config import LogLevel
from app.core.logging import (
    HANDLER_NAME,
    LOG_FORMAT,
    RequestIdFilter,
    configure_logging,
    get_request_id,
    request_id_var,
)


@pytest.fixture
def restore_root_logger() -> Iterator[None]:
    root = logging.getLogger()
    handlers, level = list(root.handlers), root.level
    yield
    root.handlers[:] = handlers
    root.setLevel(level)


def _record() -> logging.LogRecord:
    return logging.LogRecord("app.test", logging.INFO, __file__, 1, "hello", None, None)


def test_request_id_filter_outside_request_sets_dash() -> None:
    record = _record()

    assert RequestIdFilter().filter(record) is True
    assert record.request_id == "-"


def test_request_id_filter_inside_request_sets_current_id() -> None:
    token = request_id_var.set("req-123")
    try:
        record = _record()
        RequestIdFilter().filter(record)
    finally:
        request_id_var.reset(token)

    assert record.request_id == "req-123"


def test_get_request_id_default_is_dash() -> None:
    assert get_request_id() == "-"


def test_log_format_renders_request_id() -> None:
    record = _record()
    record.request_id = "abc"

    assert "INFO app.test [abc] hello" in logging.Formatter(LOG_FORMAT).format(record)


@pytest.mark.usefixtures("restore_root_logger")
def test_configure_logging_sets_level_from_setting() -> None:
    configure_logging(LogLevel.WARNING)

    assert logging.getLogger().level == logging.WARNING


@pytest.mark.usefixtures("restore_root_logger")
def test_configure_logging_called_twice_installs_one_handler() -> None:
    configure_logging(LogLevel.INFO)
    configure_logging(LogLevel.DEBUG)

    named = [h for h in logging.getLogger().handlers if h.get_name() == HANDLER_NAME]
    assert len(named) == 1
    assert any(isinstance(f, RequestIdFilter) for f in named[0].filters)
