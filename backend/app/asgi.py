"""Production ASGI entry point (design.md §18).

    uvicorn --factory app.asgi:build_app

Unlike `create_app()` (INFO logging, used by tests), this loads the real settings first, so a
missing `DATABASE_URL` fails at startup and `LOG_LEVEL` applies to the served app.
"""

from fastapi import FastAPI

from app.core.config import get_settings
from app.main import create_app


def build_app() -> FastAPI:
    """Build the app from the process environment; raises `ConfigurationError` if invalid."""
    return create_app(get_settings())
