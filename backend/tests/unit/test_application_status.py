"""Unit tests for the application status state machine (R5.2, R5.4, R5.5, design.md §6)."""

import itertools

import pytest

from app.core.errors import InvalidStatusTransitionError
from app.models.application import APPLICATION_STATUSES
from app.services.application_status import (
    ALL_STATUSES,
    ALLOWED_TRANSITIONS,
    CANONICAL_ORDER,
    SUBMITTED_STATUSES,
    ApplicationStatus,
    allowed_targets,
    is_allowed,
    transition,
)

# The design.md §6 table, written literally so the test does not trust the implementation.
EXPECTED_TABLE: dict[str, set[str]] = {
    "Saved": {"Interested", "Applied", "Withdrawn"},
    "Interested": {"Saved", "Applied", "Withdrawn"},
    "Applied": {"Assessment", "Interview", "Offer", "Rejected", "Withdrawn"},
    "Assessment": {"Interview", "Offer", "Rejected", "Withdrawn"},
    "Interview": {"Assessment", "Offer", "Rejected", "Withdrawn"},
    "Offer": {"Withdrawn"},
    "Rejected": {"Interested"},
    "Withdrawn": {"Interested"},
}
CANONICAL_NAMES = (
    "Saved",
    "Interested",
    "Applied",
    "Assessment",
    "Interview",
    "Rejected",
    "Offer",
    "Withdrawn",
)
ALL_PAIRS = list(itertools.product(CANONICAL_NAMES, repeat=2))


def test_status_enum_values_match_canonical_order_and_casing() -> None:
    assert tuple(status.value for status in ApplicationStatus) == CANONICAL_NAMES
    assert tuple(CANONICAL_ORDER) == CANONICAL_NAMES
    assert ALL_STATUSES == CANONICAL_ORDER


def test_status_enum_values_equal_model_tuple() -> None:
    assert tuple(status.value for status in ApplicationStatus) == APPLICATION_STATUSES


def test_allowed_transitions_matches_design_table() -> None:
    actual = {
        source.value: {target.value for target in targets}
        for source, targets in ALLOWED_TRANSITIONS.items()
    }
    assert actual == EXPECTED_TABLE


def test_allowed_transitions_never_contains_self_moves() -> None:
    for source, targets in ALLOWED_TRANSITIONS.items():
        assert source not in targets


@pytest.mark.parametrize(("current", "target"), ALL_PAIRS)
def test_transition_all_pairs_follow_design_table(current: str, target: str) -> None:
    source, destination = ApplicationStatus(current), ApplicationStatus(target)
    expected_allowed = current == target or target in EXPECTED_TABLE[current]

    assert is_allowed(source, destination) is expected_allowed
    if expected_allowed:
        assert transition(source, destination) is destination
    else:
        with pytest.raises(InvalidStatusTransitionError):
            transition(source, destination)


@pytest.mark.parametrize("status", list(ApplicationStatus))
def test_transition_same_status_returns_it_as_noop(status: ApplicationStatus) -> None:
    assert transition(status, status) is status


def test_transition_offer_to_applied_raises() -> None:
    with pytest.raises(InvalidStatusTransitionError) as exc_info:
        transition(ApplicationStatus.OFFER, ApplicationStatus.APPLIED)

    error = exc_info.value
    assert error.code == "INVALID_STATUS_TRANSITION"
    assert error.status_code == 409
    assert error.message == "Cannot move from Offer to Applied"
    assert error.details == {"from": "Offer", "to": "Applied", "allowed": ["Withdrawn"]}


def test_transition_saved_to_interview_raises_with_canonical_allowed_list() -> None:
    with pytest.raises(InvalidStatusTransitionError) as exc_info:
        transition(ApplicationStatus.SAVED, ApplicationStatus.INTERVIEW)

    assert exc_info.value.details == {
        "from": "Saved",
        "to": "Interview",
        "allowed": ["Interested", "Applied", "Withdrawn"],
    }


def test_allowed_targets_applied_returns_canonical_order() -> None:
    assert allowed_targets(ApplicationStatus.APPLIED) == (
        ApplicationStatus.ASSESSMENT,
        ApplicationStatus.INTERVIEW,
        ApplicationStatus.REJECTED,
        ApplicationStatus.OFFER,
        ApplicationStatus.WITHDRAWN,
    )


@pytest.mark.parametrize("status", list(ApplicationStatus))
def test_allowed_targets_every_status_sorted_canonically(status: ApplicationStatus) -> None:
    targets = allowed_targets(status)
    assert set(targets) == ALLOWED_TRANSITIONS[status]
    assert list(targets) == sorted(targets, key=CANONICAL_ORDER.index)


def test_submitted_statuses_are_exactly_the_sent_statuses() -> None:
    assert {status.value for status in SUBMITTED_STATUSES} == {
        "Applied",
        "Assessment",
        "Interview",
        "Offer",
        "Rejected",
    }
    assert isinstance(SUBMITTED_STATUSES, frozenset)


def test_allowed_transitions_mapping_is_immutable() -> None:
    with pytest.raises(TypeError):
        ALLOWED_TRANSITIONS[ApplicationStatus.OFFER] = frozenset()  # type: ignore[index]
    assert all(isinstance(targets, frozenset) for targets in ALLOWED_TRANSITIONS.values())
