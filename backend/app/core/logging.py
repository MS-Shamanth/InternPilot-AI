"""Logging setup and the per-request id context variable (design.md §14).

Log records carry `request_id` (or `-` outside a request). Callers must never log secrets,
request bodies, resume text or recruiter emails.
"""

import logging
import sys
from contextvars import ContextVar

from app.core.config import LogLevel

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s [%(request_id)s] %(message)s"
NO_REQUEST_ID = "-"
HANDLER_NAME = "internpilot"

request_id_var: ContextVar[str] = ContextVar("request_id", default=NO_REQUEST_ID)


def get_request_id() -> str:
    """Return the id of the request being handled, or `-` outside a request."""
    return request_id_var.get()


class RequestIdFilter(logging.Filter):
    """Attach the current request id to every record passing through the handler."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def configure_logging(level: LogLevel = LogLevel.INFO) -> None:
    """Install one stderr handler on the root logger; safe to call repeatedly."""
    root = logging.getLogger()
    for handler in [h for h in root.handlers if h.get_name() == HANDLER_NAME]:
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stderr)
    handler.set_name(HANDLER_NAME)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    handler.addFilter(RequestIdFilter())
    root.addHandler(handler)
    root.setLevel(level.value)
