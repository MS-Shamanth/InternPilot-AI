"""Consistency tests for the skill catalog (design.md §5.1, §9.1)."""

from types import MappingProxyType

import pytest

from app.services.matching import normalize_skill
from app.services.matching.skill_catalog import ALIASES, AMBIGUOUS_RESUME_TERMS, CATALOG

_AMBIGUOUS_CASINGS = sorted(
    (term, casing) for term, casings in AMBIGUOUS_RESUME_TERMS.items() for casing in casings
)


def test_catalog_has_at_least_40_entries() -> None:
    assert len(CATALOG) >= 40


def test_catalog_mappings_are_immutable() -> None:
    assert isinstance(ALIASES, MappingProxyType)
    assert isinstance(CATALOG, MappingProxyType)
    assert isinstance(AMBIGUOUS_RESUME_TERMS, MappingProxyType)
    assert all(isinstance(casings, frozenset) for casings in AMBIGUOUS_RESUME_TERMS.values())


@pytest.mark.parametrize("canonical", sorted(CATALOG))
def test_catalog_key_is_normalization_fixed_point(canonical: str) -> None:
    assert normalize_skill(canonical) == canonical


@pytest.mark.parametrize("canonical", sorted(CATALOG))
def test_catalog_key_is_not_an_alias_to_another_name(canonical: str) -> None:
    assert ALIASES.get(canonical, canonical) == canonical


@pytest.mark.parametrize("target", sorted(set(ALIASES.values())))
def test_alias_target_is_catalog_key(target: str) -> None:
    assert target in CATALOG


@pytest.mark.parametrize("target", sorted(set(ALIASES.values())))
def test_alias_target_is_fixed_point(target: str) -> None:
    assert normalize_skill(target) == target
    assert ALIASES.get(target, target) == target


@pytest.mark.parametrize("alias", sorted(ALIASES))
def test_alias_key_is_already_cleaned(alias: str) -> None:
    """Keys are stored normalized so the lookup in step 4 can match them."""
    assert alias == alias.strip().casefold()


@pytest.mark.parametrize("display", sorted(CATALOG.values()))
def test_catalog_display_name_normalizes_back_to_its_key(display: str) -> None:
    assert CATALOG[normalize_skill(display) or ""] == display


@pytest.mark.parametrize("term", sorted(AMBIGUOUS_RESUME_TERMS))
def test_ambiguous_term_is_catalog_key_or_alias(term: str) -> None:
    assert term in CATALOG or term in ALIASES


@pytest.mark.parametrize(("term", "casing"), _AMBIGUOUS_CASINGS)
def test_ambiguous_term_casing_normalizes_to_same_skill(term: str, casing: str) -> None:
    assert normalize_skill(casing) == normalize_skill(term)


def test_ambiguous_terms_match_design_list() -> None:
    assert AMBIGUOUS_RESUME_TERMS == {
        "go": {"Go", "Golang"},
        "golang": {"Golang"},
        "rest": {"REST"},
        "node": {"Node"},
        "js": {"JS"},
        "ts": {"TS"},
        "py": {"PY"},
        "ml": {"ML"},
        "dl": {"DL"},
        "r": {"R"},
        "c": {"C"},
    }
