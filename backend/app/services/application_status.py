"""Application status state machine (R5.2, R5.4, R5.5, design.md §6).

Pure and deterministic: no I/O, no clock, no ORM imports. `ApplicationService` calls
`transition()` for every status change and `GET /api/applications/meta` serves
`ALLOWED_TRANSITIONS` so the UI never duplicates these rules.
"""

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType

from app.core.errors import InvalidStatusTransitionError


class ApplicationStatus(StrEnum):
    """The eight tracker statuses, declared in canonical order with exact casing."""

    SAVED = "Saved"
    INTERESTED = "Interested"
    APPLIED = "Applied"
    ASSESSMENT = "Assessment"
    INTERVIEW = "Interview"
    REJECTED = "Rejected"
    OFFER = "Offer"
    WITHDRAWN = "Withdrawn"


CANONICAL_ORDER: tuple[ApplicationStatus, ...] = tuple(ApplicationStatus)
ALL_STATUSES = CANONICAL_ORDER

_S = ApplicationStatus

ALLOWED_TRANSITIONS: Mapping[ApplicationStatus, frozenset[ApplicationStatus]] = MappingProxyType(
    {
        _S.SAVED: frozenset({_S.INTERESTED, _S.APPLIED, _S.WITHDRAWN}),
        _S.INTERESTED: frozenset({_S.SAVED, _S.APPLIED, _S.WITHDRAWN}),
        _S.APPLIED: frozenset({_S.ASSESSMENT, _S.INTERVIEW, _S.OFFER, _S.REJECTED, _S.WITHDRAWN}),
        _S.ASSESSMENT: frozenset({_S.INTERVIEW, _S.OFFER, _S.REJECTED, _S.WITHDRAWN}),
        _S.INTERVIEW: frozenset({_S.ASSESSMENT, _S.OFFER, _S.REJECTED, _S.WITHDRAWN}),
        _S.OFFER: frozenset({_S.WITHDRAWN}),
        _S.REJECTED: frozenset({_S.INTERESTED}),
        _S.WITHDRAWN: frozenset({_S.INTERESTED}),
    }
)

# Statuses that mean the application has been sent; entering one sets `applied_at` (R5.6).
SUBMITTED_STATUSES: frozenset[ApplicationStatus] = frozenset(
    {_S.APPLIED, _S.ASSESSMENT, _S.INTERVIEW, _S.OFFER, _S.REJECTED}
)


def allowed_targets(current: ApplicationStatus) -> tuple[ApplicationStatus, ...]:
    """Statuses reachable from `current` in one move, in canonical order (self excluded)."""
    targets = ALLOWED_TRANSITIONS[current]
    return tuple(status for status in CANONICAL_ORDER if status in targets)


def is_allowed(current: ApplicationStatus, target: ApplicationStatus) -> bool:
    """True when `target` is `current` (no-op) or an allowed move from it."""
    return target == current or target in ALLOWED_TRANSITIONS[current]


def transition(current: ApplicationStatus, target: ApplicationStatus) -> ApplicationStatus:
    """Return the resulting status, or raise `InvalidStatusTransitionError` (409).

    A move to the current status is a no-op success (R5.4). The error details carry
    `from`, `to` and the canonical-ordered `allowed` targets (design.md §8.2).
    """
    if is_allowed(current, target):
        return target
    raise InvalidStatusTransitionError(
        f"Cannot move from {current.value} to {target.value}",
        details={
            "from": current.value,
            "to": target.value,
            "allowed": [status.value for status in allowed_targets(current)],
        },
    )
