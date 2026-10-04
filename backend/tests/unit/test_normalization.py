"""Unit tests for skill normalization (design.md §5.1, R1.3, R3.2)."""

import pytest

from app.services.matching import display_skill, normalize_skill, normalize_skills
from app.services.matching.skill_catalog import ALIASES, CATALOG

TRICKY_INPUTS = (
    "  (ReactJS).  ",
    '"Postgres"',
    " React ,",
    "( React )",
    "React.",
    "react..",
    "[Node.js];",
    "`C++`",
    "C#.",
    ".NET",
    "  Machine   Learning\t",
    "\uff32\uff25\uff21\uff23\uff34",  # full-width "REACT"
    "(rest).",
    "CI/CD/",
    "\uff27\uff4f\uff4c\uff41\uff4e\uff47",  # full-width "Golang"
    "ß",
    "ﬁ",
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("ReactJS", "react"),
        ("React.js", "react"),
        ("Postgres", "postgresql"),
        ("Node.js", "node.js"),
        ("C++", "c++"),
        ("C#", "c#"),
        (".NET", ".net"),
        ("Python.", "python"),
        ("Python,;", "python"),
        (" React ,", "react"),
        ("( React )", "react"),
        ("React.", "react"),
        ("  (ReactJS).  ", "react"),
        ('"Postgres"', "postgresql"),
        ("Machine   \t Learning", "machine learning"),
        ("\uff32\uff45\uff41\uff43\uff54\uff2a\uff33", "react"),  # full-width "ReactJS"
        ("\uff30\uff59\uff54\uff48\uff4f\uff4e", "python"),  # full-width "Python"
    ],
)
def test_normalize_skill_design_examples_return_canonical(raw: str, expected: str) -> None:
    assert normalize_skill(raw) == expected


def test_normalize_skill_internal_punctuation_is_preserved() -> None:
    assert normalize_skill("Spring/Boot") == "spring/boot"


def test_normalize_skill_only_one_trailing_dot_per_pass_strips_all_dots() -> None:
    assert normalize_skill("react...") == "react"


@pytest.mark.parametrize("raw", ["", "   ", "(,)", "...", "\"'`", "\t\n"])
def test_normalize_skill_empty_after_cleaning_returns_none(raw: str) -> None:
    assert normalize_skill(raw) is None


def test_normalize_skill_longer_than_50_chars_returns_none() -> None:
    assert normalize_skill("a" * 51) is None


def test_normalize_skill_exactly_50_chars_is_kept() -> None:
    assert normalize_skill("a" * 50) == "a" * 50


def test_normalize_skill_length_is_measured_after_cleaning() -> None:
    assert normalize_skill("  " + "a" * 50 + " ,") == "a" * 50


@pytest.mark.parametrize(("alias", "canonical"), sorted(ALIASES.items()))
def test_normalize_skill_alias_maps_to_canonical(alias: str, canonical: str) -> None:
    assert normalize_skill(alias) == canonical


@pytest.mark.parametrize(
    "raw", [*CATALOG.keys(), *ALIASES.keys(), *ALIASES.values(), *TRICKY_INPUTS]
)
def test_normalize_skill_is_idempotent(raw: str) -> None:
    once = normalize_skill(raw)

    assert once is not None
    assert normalize_skill(once) == once


def test_normalize_skills_collapses_duplicates_and_variants() -> None:
    result = normalize_skills(["React", "reactjs", " (React.js) ", "Postgres", "PostgreSQL"])

    assert result == frozenset({"react", "postgresql"})


def test_normalize_skills_drops_empty_results() -> None:
    assert normalize_skills(["(,)", "", "Python"]) == frozenset({"python"})


def test_normalize_skills_empty_input_returns_empty_frozenset() -> None:
    assert normalize_skills([]) == frozenset()


@pytest.mark.parametrize(
    ("canonical", "expected"),
    [
        ("react", "React"),
        ("postgresql", "PostgreSQL"),
        ("node.js", "Node.js"),
        ("machine learning", "Machine Learning"),
        ("c#", "C#"),
        (".net", ".NET"),
        ("rest apis", "REST APIs"),
    ],
)
def test_display_skill_catalog_entry_returns_display_name(canonical: str, expected: str) -> None:
    assert display_skill(canonical) == expected


def test_display_skill_unknown_skill_title_cases_each_word() -> None:
    assert display_skill("quantum annealing") == "Quantum Annealing"


def test_display_skill_unknown_skill_keeps_rest_of_word() -> None:
    assert display_skill("svelteKit 2.0") == "SvelteKit 2.0"


def test_display_skill_unknown_skill_with_symbol_prefix_is_unchanged() -> None:
    assert display_skill("#hashtag") == "#hashtag"
