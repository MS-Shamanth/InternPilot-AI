"""Application factory for the InternPilot AI FastAPI app."""

from collections.abc import Sequence

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp

from app.api.router import api_router
from app.core.config import DEFAULT_CORS_ORIGINS, LogLevel, Settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import REQUEST_ID_HEADER, BodySizeLimitMiddleware, RequestIdMiddleware
from app.core.version import APP_VERSION

APP_TITLE = "InternPilot AI"
CORS_ALLOWED_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS")
CORS_ALLOWED_HEADERS = ("Content-Type", "Accept", "X-Demo-User", REQUEST_ID_HEADER)
CORS_EXPOSED_HEADERS = (REQUEST_ID_HEADER,)


class InternPilotApp(FastAPI):
    """FastAPI app whose outer layers are `RequestIdMiddleware` and then `CORSMiddleware`.

    Starlette always places `ServerErrorMiddleware` outside user middleware, so wrapping the
    built stack is what guarantees `X-Request-ID` (R12.5) and the CORS headers on 500 responses
    as well; without them a browser could not read the error envelope of a cross-origin 500.
    Preflight requests are answered by `CORSMiddleware` and still carry `X-Request-ID`.
    """

    def __init__(self, *, cors_origins: Sequence[str], title: str, version: str) -> None:
        super().__init__(title=title, version=version)
        self.cors_origins = tuple(cors_origins)

    def build_middleware_stack(self) -> ASGIApp:
        with_cors = CORSMiddleware(
            super().build_middleware_stack(),
            allow_origins=self.cors_origins,
            allow_credentials=False,
            allow_methods=CORS_ALLOWED_METHODS,
            allow_headers=CORS_ALLOWED_HEADERS,
            expose_headers=CORS_EXPOSED_HEADERS,
        )
        return RequestIdMiddleware(with_cors)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build a configured app; `settings` drives the log level and CORS origins.

    When omitted (tests), INFO logging and `DEFAULT_CORS_ORIGINS` apply.
    """
    configure_logging(settings.log_level if settings is not None else LogLevel.INFO)
    cors_origins = settings.cors_origins if settings is not None else DEFAULT_CORS_ORIGINS
    app = InternPilotApp(cors_origins=cors_origins, title=APP_TITLE, version=APP_VERSION)
    app.add_middleware(BodySizeLimitMiddleware)
    register_exception_handlers(app)
    app.include_router(api_router)
    return app
