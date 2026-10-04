"""Pure resume-analysis rules (design.md §9.1-§9.3, R8). No I/O, clock or randomness."""

import re
import unicodedata
from collections import Counter
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass

from app.schemas.resume import (
    ResumeMissingSkill,
    ResumeRelevantProject,
    ResumeSuggestion,
    ResumeSuggestionRule,
)
from app.services.matching.normalization import normalize_skill
from app.services.matching.skill_catalog import ALIASES, AMBIGUOUS_RESUME_TERMS, CATALOG

MAX_MISSING_KEYWORDS = 15
KEYWORDS_IN_SUGGESTION = 5
MIN_KEYWORDS_FOR_SUGGESTION = 3
MIN_KEYWORD_FREQUENCY = 2
MIN_KEYWORD_LENGTH = 3
MIN_NUMERIC_TOKENS = 3
SHORT_RESUME_WORDS = 150
LONG_RESUME_WORDS = 1_200

STOP_WORDS = frozenset(
    {
        "about", "above", "across", "after", "all", "also", "among", "and", "any", "are",
        "as", "been", "being", "both", "but", "can", "could", "did", "does", "each", "etc",
        "for", "from", "had", "has", "have", "help", "how", "into", "its", "may", "more",
        "most", "must", "not", "of", "on", "or", "other", "our", "out", "over", "own",
        "per", "should", "some", "such", "than", "that", "the", "their", "them", "then",
        "there", "these", "they", "this", "those", "through", "to", "under", "using", "very",
        "was", "way", "we", "well", "were", "what", "when", "where", "which", "while", "who",
        "why", "will", "with", "within", "without", "would", "you", "your",
    }
)  # fmt: skip

_WHITESPACE_RUN = re.compile(r"\s+")
_BOUNDARY_BEFORE = r"(?<![A-Za-z0-9+#.])"
_BOUNDARY_AFTER = r"(?![A-Za-z0-9+#])"
_KEYWORD = re.compile(r"[a-z][a-z0-9+#.]{2,}")
_NUMERIC = re.compile(r"[0-9%]")


@dataclass(frozen=True)
class ResumeText:
    """`nfkc`: NFKC + collapsed whitespace, case kept; `folded`: its casefold."""

    nfkc: str
    folded: str


def resume_views(text: str) -> ResumeText:
    nfkc = _WHITESPACE_RUN.sub(" ", unicodedata.normalize("NFKC", text)).strip()
    return ResumeText(nfkc=nfkc, folded=nfkc.casefold())


def _contains_term(haystack: str, term: str) -> bool:
    pattern = _BOUNDARY_BEFORE + re.escape(term) + _BOUNDARY_AFTER
    return re.search(pattern, haystack) is not None


def _has_term(resume: ResumeText, term: str) -> bool:
    """Ambiguous short terms match case-sensitively in their accepted casings (§9.1)."""
    casings = AMBIGUOUS_RESUME_TERMS.get(term)
    if casings is None:
        return _contains_term(resume.folded, term)
    return any(_contains_term(resume.nfkc, casing) for casing in casings)


def extract_resume_skills(resume: ResumeText, extra_skills: Iterable[str] = ()) -> frozenset[str]:
    """Canonical skills found as whole words/phrases; catalog = `CATALOG` | `extra_skills`."""
    terms: dict[str, str] = {name: name for name in (*CATALOG, *extra_skills)}
    terms.update(ALIASES)
    return frozenset(
        canonical for term, canonical in terms.items() if term and _has_term(resume, term)
    )


def word_count(resume: ResumeText) -> int:
    return len(resume.nfkc.split())


def numeric_token_count(resume: ResumeText) -> int:
    """Whitespace tokens containing a digit or `%`."""
    return sum(1 for token in resume.nfkc.split() if _NUMERIC.search(token))


def _keywords(text: str) -> Iterator[str]:
    folded = unicodedata.normalize("NFKC", text).casefold()
    for match in _KEYWORD.findall(folded):
        token = match.rstrip(".")
        if len(token) >= MIN_KEYWORD_LENGTH:
            yield token


def missing_keywords(description: str, resume: ResumeText, catalog: frozenset[str]) -> list[str]:
    """Job terms absent from the resume: frequent (≥ 2) or catalog skills; freq desc, then a-z."""
    present = set(_keywords(resume.folded))
    counts = Counter(
        token
        for token in _keywords(description)
        if token not in STOP_WORDS and token not in present
    )
    kept = [
        token
        for token, count in counts.items()
        if count >= MIN_KEYWORD_FREQUENCY or normalize_skill(token) in catalog
    ]
    return sorted(kept, key=lambda token: (-counts[token], token))[:MAX_MISSING_KEYWORDS]


def link_in_resume(url: str, resume: ResumeText) -> bool:
    """Whether the link appears in the resume, ignoring scheme, `www.` and a trailing slash."""
    core = url.casefold().split("://", 1)[-1].rstrip("/").removeprefix("www.")
    return bool(core) and core in resume.folded


def _evidence_key(suggestion: ResumeSuggestion) -> tuple[str, ...]:
    return tuple(item.casefold() for item in suggestion.evidence)


def _sorted(suggestions: Iterable[ResumeSuggestion]) -> list[ResumeSuggestion]:
    return sorted(suggestions, key=_evidence_key)


def _skill_suggestions(missing: Sequence[ResumeMissingSkill]) -> list[ResumeSuggestion]:
    in_profile = _sorted(
        ResumeSuggestion(
            rule=ResumeSuggestionRule.ADD_PROFILE_SKILL,
            message=(
                f"Your profile lists {item.skill}, which this role "
                f"{'requires' if item.is_required else 'prefers'}, "
                "but your resume does not mention it."
            ),
            evidence=[item.skill],
        )
        for item in missing
        if item.in_profile
    )
    gaps = _sorted(
        ResumeSuggestion(
            rule=ResumeSuggestionRule.GAP_REQUIRED_SKILL,
            message=(
                f"{item.skill} is required and not evidenced; "
                "consider a project or course that demonstrates it."
            ),
            evidence=[item.skill],
        )
        for item in missing
        if item.is_required and not item.in_profile
    )
    return in_profile + gaps


def _project_suggestions(projects: Sequence[ResumeRelevantProject]) -> list[ResumeSuggestion]:
    return _sorted(
        ResumeSuggestion(
            rule=ResumeSuggestionRule.MENTION_PROJECT,
            message=(
                f'Mention your project "{project.name}"; '
                f"it uses {', '.join(project.matched_skills)}."
            ),
            evidence=[project.name],
        )
        for project in projects
        if not project.mentioned_in_resume
    )


def _text_suggestions(
    keywords: Sequence[str], words: int, numeric_tokens: int
) -> list[ResumeSuggestion]:
    suggestions: list[ResumeSuggestion] = []
    if len(keywords) >= MIN_KEYWORDS_FOR_SUGGESTION:
        top = list(keywords[:KEYWORDS_IN_SUGGESTION])
        suggestions.append(
            ResumeSuggestion(
                rule=ResumeSuggestionRule.ADD_KEYWORDS,
                message=f"Consider reflecting these job terms where truthful: {', '.join(top)}.",
                evidence=top,
            )
        )
    if numeric_tokens < MIN_NUMERIC_TOKENS:
        suggestions.append(
            ResumeSuggestion(
                rule=ResumeSuggestionRule.QUANTIFY,
                message=f"Add measurable outcomes (numbers, percentages); found {numeric_tokens}.",
                evidence=[str(numeric_tokens)],
            )
        )
    length_rule: ResumeSuggestionRule | None = None
    if words < SHORT_RESUME_WORDS:
        length_rule = ResumeSuggestionRule.LENGTH_SHORT
    elif words > LONG_RESUME_WORDS:
        length_rule = ResumeSuggestionRule.LENGTH_LONG
    if length_rule is not None:
        suggestions.append(
            ResumeSuggestion(
                rule=length_rule,
                message=f"Resume has {words} words; aim for 300\u2013900 for early-career roles.",
                evidence=[str(words)],
            )
        )
    return suggestions


def _link_suggestions(links: Mapping[str, str], resume: ResumeText) -> list[ResumeSuggestion]:
    """`links` maps a label (`GitHub`, `portfolio`) to the profile URL."""
    return _sorted(
        ResumeSuggestion(
            rule=ResumeSuggestionRule.ADD_LINKS,
            message=f"Add your {label} link.",
            evidence=[url],
        )
        for label, url in links.items()
        if not link_in_resume(url, resume)
    )


def build_suggestions(
    *,
    missing: Sequence[ResumeMissingSkill],
    projects: Sequence[ResumeRelevantProject],
    keywords: Sequence[str],
    resume: ResumeText,
    links: Mapping[str, str],
) -> list[ResumeSuggestion]:
    """Every §9.3 rule in table order; within a rule, by evidence alphabetically."""
    return [
        *_skill_suggestions(missing),
        *_project_suggestions(projects),
        *_text_suggestions(keywords, word_count(resume), numeric_token_count(resume)),
        *_link_suggestions(links, resume),
    ]
