"""Shared FastAPI dependencies: clock and current demo user (design.md §13.2, R13.2-R13.4).

The `X-Demo-User` mechanism is a single-user demo convenience, NOT authentication. Anyone who
can reach the API can act as any existing user. Do not expose it on a public network.
"""

import logging
import re
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.clock import Clock, SystemClock
from app.core.database import get_session
from app.core.errors import DemoUserNotSeededError, UnknownDemoUserError
from app.models import User
from app.models.user import DEMO_SEED_KEY
from app.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)

DEMO_USER_HEADER = "X-Demo-User"
EMAIL_MAX_LENGTH = 254
# Deliberately loose: stored emails are validated on write, so anything that is not
# `local@domain` can never match a user and is rejected without a query.
_EMAIL_SHAPE = re.compile(r"^[^@\s]+@[^@\s]+$")

DemoUserHeader = Annotated[str | None, Header(alias=DEMO_USER_HEADER, max_length=EMAIL_MAX_LENGTH)]


def get_clock() -> Clock:
    """Current time source; tests override this with a `FixedClock`."""
    return SystemClock()


def get_current_user(
    session: Annotated[Session, Depends(get_session)],
    x_demo_user: DemoUserHeader = None,
) -> User:
    """Resolve the acting user.

    - Header present: the user whose email equals the header value (trimmed, lowercase), else
      401 `UNKNOWN_DEMO_USER`. Values longer than 254 characters fail validation (422).
    - Header absent: the seeded user with `seed_key='demo'` (its email may have been edited,
      R13.2a), else 503 `DEMO_USER_NOT_SEEDED`.
    """
    users = UserRepository(session)
    if x_demo_user is not None:
        email = x_demo_user.strip().lower()
        user = users.get_by_email(email) if _EMAIL_SHAPE.fullmatch(email) else None
        if user is None:
            # The header value is not logged: it is user-supplied and may be personal data.
            logger.warning("Unknown %s header value", DEMO_USER_HEADER)
            raise UnknownDemoUserError
        return user
    user = users.get_by_seed_key(DEMO_SEED_KEY)
    if user is None:
        logger.warning("Default demo user (seed_key=%r) is not seeded", DEMO_SEED_KEY)
        raise DemoUserNotSeededError
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
SessionDep = Annotated[Session, Depends(get_session)]
ClockDep = Annotated[Clock, Depends(get_clock)]
