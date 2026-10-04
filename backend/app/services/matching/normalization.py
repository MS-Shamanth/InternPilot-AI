"""Skill normalization (design.md §5.1, R3.2). Pure: no I/O, no clock, no randomness."""

import re
import unicodedata
from collections.abc import Iterable

from app.services.matching.skill_catalog import ALIASES, CATALOG

EDGE_PUNCTUATION = ",;:|/\\()[]{}\"'`"
MAX_SKILL_LENGTH = 50

_WHITESPACE_RUN = re.compile(r"\s+")
# NFKC + casefold reaches a fixed point within two or three passes for any real text; the cap
# only guarantees termination. Property tests check idempotence over arbitrary Unicode.
_MAX_PASSES = 16


def _strip_edges(text: str) -> str:
    """Step 3: strip whitespace, edge punctuation and one trailing '.' until nothing changes."""
    while True:
        stripped = text.strip().strip(EDGE_PUNCTUATION)
        if stripped.endswith("."):
            stripped = stripped[:-1]
        if stripped == text:
            return text
        text = stripped


def _clean(text: str) -> str:
    """Steps 1-4 of §5.1: NFKC + casefold, collapse whitespace, strip edges, resolve aliases."""
    folded = unicodedata.normalize("NFKC", text).casefold()
    collapsed = _WHITESPACE_RUN.sub(" ", folded)
    stripped = _strip_edges(collapsed)
    return ALIASES.get(stripped, stripped)


def normalize_skill(raw: str) -> str | None:
    """Canonical skill name for `raw`, or None if it is empty or longer than 50 characters.

    The cleaning steps repeat until the text stops changing, so the result is a fixed point:
    `normalize_skill(normalize_skill(x)) == normalize_skill(x)` whenever the inner result is
    not None.
    """
    text = raw
    for _ in range(_MAX_PASSES):
        cleaned = _clean(text)
        if cleaned == text:
            break
        text = cleaned
    if not text or len(text) > MAX_SKILL_LENGTH:
        return None
    return text


def normalize_skills(raws: Iterable[str]) -> frozenset[str]:
    """Normalized names for `raws`; duplicates collapse and None results are dropped."""
    return frozenset(name for name in map(normalize_skill, raws) if name is not None)


def display_skill(canonical: str) -> str:
    """Catalog display name, else each space-separated word with its first character uppercased."""
    display = CATALOG.get(canonical)
    if display is not None:
        return display
    return " ".join(word[:1].upper() + word[1:] for word in canonical.split(" "))
