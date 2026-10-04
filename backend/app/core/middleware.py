"""Pure ASGI middleware: request ids + access log (R12.5, §14) and body size limit (§8.1).

Both are plain ASGI callables rather than `BaseHTTPMiddleware` so request bodies stay streamed
and the response `send` channel can be wrapped reliably.
"""

import json
import logging
import re
import time
import uuid

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import PayloadTooLargeError, error_envelope
from app.core.logging import request_id_var

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"
REQUEST_ID_PATTERN = re.compile(r"[A-Za-z0-9-]{1,64}")
MAX_REQUEST_BODY_BYTES = 5_000_000
PAYLOAD_TOO_LARGE_CODE = PayloadTooLargeError.default_code


def resolve_request_id(incoming: str | None) -> str:
    """Reuse a safe incoming id (`^[A-Za-z0-9-]{1,64}$`), otherwise generate a UUID4 hex."""
    if incoming is not None and REQUEST_ID_PATTERN.fullmatch(incoming):
        return incoming
    return uuid.uuid4().hex


class RequestIdMiddleware:
    """Assign a request id, expose it to logging and add `X-Request-ID` to every response.

    Installed outside Starlette's `ServerErrorMiddleware` (see `app.main`), so 500 responses
    carry the header too. Emits one INFO access line per request.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = resolve_request_id(Headers(scope=scope).get(REQUEST_ID_HEADER))
        token = request_id_var.set(request_id)
        started_at = time.perf_counter()
        status_code = 500

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            duration_ms = (time.perf_counter() - started_at) * 1000
            logger.info("%s %s %d %.1fms", scope["method"], scope["path"], status_code, duration_ms)
            request_id_var.reset(token)


class _BodyTooLargeError(Exception):
    """Internal signal raised from `receive` once the streamed body exceeds the limit."""


def _payload_too_large_body(max_bytes: int) -> bytes:
    envelope = error_envelope(
        PAYLOAD_TOO_LARGE_CODE,
        f"Request body exceeds the maximum size of {max_bytes} bytes.",
        {"max_bytes": max_bytes},
    )
    return json.dumps(envelope).encode("utf-8")


async def _send_payload_too_large(send: Send, max_bytes: int) -> None:
    body = _payload_too_large_body(max_bytes)
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


def _declared_length(scope: Scope) -> int | None:
    value = Headers(scope=scope).get("content-length")
    if value is None or not value.isdigit():
        return None
    return int(value)


class BodySizeLimitMiddleware:
    """Reject request bodies larger than `max_bytes` with 413 `PAYLOAD_TOO_LARGE`.

    Checks the declared `Content-Length` up front and counts streamed bytes (chunked or
    mis-declared bodies). Once the limit is crossed, whatever the app tries to send is
    discarded and the 413 envelope is sent instead.
    """

    def __init__(self, app: ASGIApp, max_bytes: int = MAX_REQUEST_BODY_BYTES) -> None:
        if max_bytes < 1:
            raise ValueError("max_bytes must be positive")
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        declared = _declared_length(scope)
        if declared is not None and declared > self.max_bytes:
            await _send_payload_too_large(send, self.max_bytes)
            return

        received_bytes = 0
        exceeded = False
        response_started = False

        async def limited_receive() -> Message:
            nonlocal received_bytes, exceeded
            message = await receive()
            if message["type"] == "http.request":
                received_bytes += len(message.get("body", b""))
                if received_bytes > self.max_bytes:
                    exceeded = True
                    raise _BodyTooLargeError
            return message

        async def guarded_send(message: Message) -> None:
            nonlocal response_started
            if exceeded and not response_started:
                return
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, guarded_send)
        except _BodyTooLargeError:
            if response_started:
                raise
        if exceeded and not response_started:
            await _send_payload_too_large(send, self.max_bytes)
