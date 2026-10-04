"""Command-line entry points (design.md §12, §18).

    python -m app.cli seed
    python -m app.cli ingest --source {fixture,remotive,arbeitnow} [--no-fallback] [--limit N]

Both use the real settings, database and system clock, log their summary and exit 0 on success
or 1 with a logged error on failure (2 for invalid arguments, from argparse).
"""

import argparse
import logging
import sys
from collections.abc import Sequence

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.clock import SystemClock
from app.core.config import ConfigurationError, Settings, get_settings
from app.core.database import create_db_engine, create_session_factory
from app.core.errors import AppError
from app.core.logging import configure_logging
from app.schemas.ingest import (
    INGEST_LIMIT_DEFAULT,
    INGEST_MAX_ITEMS,
    IngestRequest,
    IngestSourceName,
)
from app.services.ingestion.service import IngestionService, default_sources
from app.services.seed_service import SeedService, require_demo_user

logger = logging.getLogger("app.cli")

EXIT_OK = 0
EXIT_FAILURE = 1
CLI_SOURCES = (IngestSourceName.FIXTURE, IngestSourceName.REMOTIVE, IngestSourceName.ARBEITNOW)


def _limit(value: str) -> int:
    try:
        limit = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be an integer") from None
    if not 1 <= limit <= INGEST_MAX_ITEMS:
        raise argparse.ArgumentTypeError(f"must be between 1 and {INGEST_MAX_ITEMS}")
    return limit


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="InternPilot AI tasks")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("seed", help="load the demo user, jobs and applications (idempotent)")
    ingest = commands.add_parser("ingest", help="import jobs from a public API or local fixtures")
    ingest.add_argument("--source", required=True, choices=[source.value for source in CLI_SOURCES])
    ingest.add_argument(
        "--no-fallback",
        action="store_true",
        help="fail instead of falling back to local fixtures when a public source is down",
    )
    ingest.add_argument(
        "--limit",
        type=_limit,
        default=INGEST_LIMIT_DEFAULT,
        help=f"maximum items to import (1-{INGEST_MAX_ITEMS}, default {INGEST_LIMIT_DEFAULT})",
    )
    return parser


def _seed(session: Session, settings: Settings) -> None:
    SeedService(session, SystemClock(), settings).run()


def _ingest(session: Session, settings: Settings, args: argparse.Namespace) -> None:
    request = IngestRequest(
        source=IngestSourceName(args.source), fallback=not args.no_fallback, limit=args.limit
    )
    user = require_demo_user(session)
    IngestionService(session, SystemClock(), default_sources(settings)).ingest(user, request)


def main(argv: Sequence[str] | None = None) -> int:
    """Run one command; returns the process exit code."""
    args = build_parser().parse_args(argv)
    configure_logging()
    try:
        settings = get_settings()
    except ConfigurationError as error:
        logger.error("%s", error)
        return EXIT_FAILURE
    configure_logging(settings.log_level)
    engine = create_db_engine(settings.database_url.get_secret_value())
    try:
        with create_session_factory(engine)() as session:
            if args.command == "seed":
                _seed(session, settings)
            else:
                _ingest(session, settings, args)
    except AppError as error:
        logger.error("%s failed: %s (%s)", args.command, error.message, error.code)
        if error.details:
            logger.error("%s failure details: %s", args.command, error.details)
        return EXIT_FAILURE
    except SQLAlchemyError:
        logger.exception("%s failed: database error", args.command)
        return EXIT_FAILURE
    finally:
        engine.dispose()
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
