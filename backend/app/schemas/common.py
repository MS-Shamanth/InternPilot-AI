"""Shared schema building blocks: base models, enums and constrained types (design.md §8.1)."""

from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated
from urllib.parse import urlsplit

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    PlainSerializer,
    StringConstraints,
)

URL_MAX_LENGTH = 300
HTTP_SCHEMES = frozenset({"http", "https"})


class RequestModel(BaseModel):
    """Base for every request body: unknown fields are rejected (R12.4)."""

    model_config = ConfigDict(extra="forbid")


class WorkMode(StrEnum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"


class ExperienceLevel(StrEnum):
    INTERNSHIP = "internship"
    ENTRY = "entry"
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"


class EducationLevel(StrEnum):
    HIGH_SCHOOL = "high_school"
    DIPLOMA = "diploma"
    BACHELOR = "bachelor"
    MASTER = "master"
    PHD = "phd"


class EmploymentType(StrEnum):
    INTERNSHIP = "internship"
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"


class JobSource(StrEnum):
    SEED = "seed"
    FIXTURE = "fixture"
    REMOTIVE = "remotive"
    ARBEITNOW = "arbeitnow"
    PAYLOAD = "payload"


class SalaryPeriod(StrEnum):
    YEAR = "year"
    MONTH = "month"
    HOUR = "hour"


def blank_to_none(value: object) -> object:
    """Treat an empty or whitespace-only string as "not provided" for optional fields."""
    if isinstance(value, str) and not value.strip():
        return None
    return value


def dedupe_casefold(values: list[str]) -> list[str]:
    """Drop later entries that equal an earlier one ignoring case; keeps first spelling/order."""
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        key = value.casefold()
        if key not in seen:
            seen.add(key)
            unique.append(value)
    return unique


def require_unique[T](values: list[T]) -> list[T]:
    """Reject lists with repeated items."""
    if len(set(values)) != len(values):
        raise ValueError("Items must be unique")
    return values


def validate_http_url(value: str) -> str:
    """Accept only absolute `http`/`https` URLs with a host and no embedded credentials.

    Error messages never include the submitted value.
    """
    if any(character.isspace() for character in value):
        raise ValueError("URL must not contain whitespace")
    try:
        parts = urlsplit(value)
        _ = parts.port  # raises ValueError for a non-numeric or out-of-range port
    except ValueError:
        raise ValueError("URL is not valid") from None
    if parts.scheme.lower() not in HTTP_SCHEMES:
        raise ValueError("URL must use http or https")
    if not parts.hostname:
        raise ValueError("URL must include a host")
    if parts.username is not None or parts.password is not None:
        raise ValueError("URL must not include credentials")
    return value


def require_host(allowed_hosts: frozenset[str]) -> Callable[[str], str]:
    """Validator factory: the URL's host (case-insensitive) must be one of `allowed_hosts`."""
    expected = " or ".join(sorted(allowed_hosts))

    def check(value: str) -> str:
        if urlsplit(value).hostname not in allowed_hosts:
            raise ValueError(f"URL host must be {expected}")
        return value

    return check


def format_utc(value: datetime) -> str:
    """ISO-8601 in UTC with a `Z` suffix (e.g. `2025-01-15T09:30:00Z`)."""
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


HttpUrl = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=URL_MAX_LENGTH),
    AfterValidator(validate_http_url),
]
"""An http(s) URL kept as the submitted (trimmed) string."""

OptionalHttpUrl = Annotated[HttpUrl | None, BeforeValidator(blank_to_none)]
"""An optional http(s) URL; blank strings become `None`."""

UtcDateTime = Annotated[datetime, PlainSerializer(format_utc, return_type=str, when_used="json")]
"""A timestamp serialized as ISO-8601 UTC with `Z`."""
