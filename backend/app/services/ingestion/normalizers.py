"""Raw job item → validated `JobCreate` or `Rejection` (R10.4, design.md §11.3, §11.4).

Pure: no I/O, no clock (callers pass `today`). External text is untrusted: HTML is reduced to
plain text, entities unescaped, whitespace collapsed and the description truncated.
"""

import hashlib
import re
import unicodedata
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from html.parser import HTMLParser

from pydantic import ValidationError

from app.schemas.common import EmploymentType, ExperienceLevel, JobSource, WorkMode
from app.schemas.ingest import DESCRIPTION_MAX_LENGTH, JobCreate, RawFormat
from app.services.matching.normalization import normalize_skill
from app.services.matching.skill_catalog import ALIASES, AMBIGUOUS_RESUME_TERMS, CATALOG

TAG_SKILLS_MAX = 15
DESCRIPTION_SKILLS_MAX = 10
REASON_MAX_LENGTH = 300
DEFAULT_REMOTE_LOCATION = "Remote"

type RawFields = dict[str, object]

_WHITESPACE_RUN = re.compile(r"\s+")
_WORD_TOKEN = re.compile(r"[^\W_]+")
_SKIPPED_TAGS = frozenset({"script", "style", "template"})
# Tags that separate words; inline tags (`b`, `a`, `span`, ...) join their text directly.
_BLOCK_TAGS = frozenset(
    {
        "address",
        "article",
        "aside",
        "blockquote",
        "br",
        "dd",
        "div",
        "dl",
        "dt",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "hr",
        "li",
        "ol",
        "p",
        "pre",
        "section",
        "table",
        "td",
        "th",
        "tr",
        "ul",
    }
)
_BOUNDARY_BEFORE = r"(?<![A-Za-z0-9+#.])"
_BOUNDARY_AFTER = r"(?![A-Za-z0-9+#])"

REMOTIVE_EMPLOYMENT_TYPES: Mapping[str, EmploymentType] = {
    "full_time": EmploymentType.FULL_TIME,
    "part_time": EmploymentType.PART_TIME,
    "contract": EmploymentType.CONTRACT,
    "freelance": EmploymentType.CONTRACT,
    "internship": EmploymentType.INTERNSHIP,
}

# Whole title words (not substrings, so "Internal Tools" is not an internship).
INTERNSHIP_TITLE_WORDS = frozenset({"intern", "internship", "trainee"})
# Checked in order; the first level with a matching title word or phrase wins (§11.3).
EXPERIENCE_TITLE_RULES: tuple[tuple[ExperienceLevel, frozenset[str]], ...] = (
    (ExperienceLevel.INTERNSHIP, INTERNSHIP_TITLE_WORDS),
    (ExperienceLevel.ENTRY, frozenset({"graduate", "entry", "new grad"})),
    (ExperienceLevel.JUNIOR, frozenset({"junior", "jr"})),
    (ExperienceLevel.MID, frozenset({"mid", "intermediate"})),
    (ExperienceLevel.SENIOR, frozenset({"senior", "sr", "lead", "principal", "staff"})),
)

NORMALIZED_TEXT_FIELDS = (
    "title",
    "company",
    "location",
    "employment_type",
    "work_mode",
    "experience_level",
    "min_education_level",
    "salary_currency",
    "salary_period",
)
NORMALIZED_PASSTHROUGH_FIELDS = (
    "salary_min",
    "salary_max",
    "deadline",
    "required_skills",
    "preferred_skills",
)


@dataclass(frozen=True)
class Rejection:
    """An item that could not be ingested; `reason` never contains the raw input."""

    index: int
    reason: str


class _ItemRejectedError(Exception):
    """Internal: a mapping step found the item unusable before validation."""


# --- text ----------------------------------------------------------------------------------


class _TextExtractor(HTMLParser):
    """Collect text content; tag boundaries become spaces, script/style content is dropped."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIPPED_TAGS:
            self._skip_depth += 1
        if tag in _BLOCK_TAGS:
            self._parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIPPED_TAGS and self._skip_depth:
            self._skip_depth -= 1
        if tag in _BLOCK_TAGS:
            self._parts.append(" ")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self._parts.append(data)

    def text(self) -> str:
        return "".join(self._parts)


def collapse_whitespace(text: str) -> str:
    return _WHITESPACE_RUN.sub(" ", text).strip()


def html_to_text(markup: str) -> str:
    """Plain text of `markup`: tags removed, entities unescaped, whitespace collapsed."""
    extractor = _TextExtractor()
    extractor.feed(markup)
    extractor.close()
    return collapse_whitespace(extractor.text())


def clean_description(markup: str) -> str:
    """`html_to_text` truncated to the stored maximum (20,000 characters)."""
    return html_to_text(markup)[:DESCRIPTION_MAX_LENGTH]


# --- fingerprint (§11.4) -------------------------------------------------------------------


def _fingerprint_part(text: str) -> str:
    """casefold, non-alphanumerics → space, collapse, strip."""
    spaced = "".join(char if char.isalnum() else " " for char in text.casefold())
    return " ".join(spaced.split())


def fingerprint(title: str, company: str, location: str) -> str:
    """sha256 hex of the normalized `title|company|location`."""
    key = "|".join(_fingerprint_part(part) for part in (title, company, location))
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


# --- skills --------------------------------------------------------------------------------


def _term_pattern(term: str) -> re.Pattern[str]:
    return re.compile(_BOUNDARY_BEFORE + re.escape(term) + _BOUNDARY_AFTER)


def _build_patterns() -> (
    tuple[tuple[tuple[re.Pattern[str], str], ...], tuple[tuple[re.Pattern[str], str], ...]]
):
    """(folded, cased) patterns for every catalog name and alias, per the §9.1 rules: ambiguous
    short terms only match their accepted casings; everything else matches casefolded text."""
    terms: dict[str, str] = {name: name for name in CATALOG} | dict(ALIASES)
    folded: list[tuple[re.Pattern[str], str]] = []
    cased: list[tuple[re.Pattern[str], str]] = []
    for term, canonical in sorted(terms.items()):
        casings = AMBIGUOUS_RESUME_TERMS.get(term)
        if casings is None:
            folded.append((_term_pattern(term), canonical))
        else:
            cased.extend((_term_pattern(casing), canonical) for casing in sorted(casings))
    return tuple(folded), tuple(cased)


_FOLDED_PATTERNS, _CASED_PATTERNS = _build_patterns()


def catalog_skills_in(text: str) -> frozenset[str]:
    """Canonical catalog skills mentioned in `text` as whole words or phrases."""
    nfkc = collapse_whitespace(unicodedata.normalize("NFKC", text))
    folded = nfkc.casefold()
    found = {canonical for pattern, canonical in _FOLDED_PATTERNS if pattern.search(folded)}
    found.update(canonical for pattern, canonical in _CASED_PATTERNS if pattern.search(nfkc))
    return frozenset(found)


def _tag_skills(tags: object) -> list[str]:
    """Normalized tags in first-seen order (unusable tags dropped), at most 15."""
    if not isinstance(tags, list):
        return []
    names: list[str] = []
    for tag in tags:
        name = normalize_skill(tag) if isinstance(tag, str) else None
        if name is not None and name not in names:
            names.append(name)
    return names[:TAG_SKILLS_MAX]


def _description_skills(description: str, required: list[str]) -> list[str]:
    """Catalog skills found in the description and not required, by name, at most 10."""
    found = catalog_skills_in(description) - set(required)
    return sorted(found)[:DESCRIPTION_SKILLS_MAX]


# --- field helpers -------------------------------------------------------------------------


def _text(value: object) -> str | None:
    """A display string from untrusted text: HTML stripped, whitespace collapsed."""
    if isinstance(value, str):
        return html_to_text(value) or None
    return None


def _identifier(value: object) -> str | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return collapse_whitespace(value) or None
    return None


def _url(value: object) -> str | None:
    if isinstance(value, str):
        return collapse_whitespace(value) or None
    return None


def _description(value: object) -> str:
    return clean_description(value) if isinstance(value, str) else ""


def _title_words(title: str) -> tuple[frozenset[str], str]:
    words = _WORD_TOKEN.findall(title.casefold())
    return frozenset(words), f" {' '.join(words)} "


def _has_title_term(title: str, terms: frozenset[str]) -> bool:
    words, joined = _title_words(title)
    return any(term in words if " " not in term else f" {term} " in joined for term in terms)


def infer_experience_level(title: str) -> ExperienceLevel | None:
    """Experience level implied by the job title, or None (§11.3)."""
    for level, terms in EXPERIENCE_TITLE_RULES:
        if _has_title_term(title, terms):
            return level
    return None


def is_internship_title(title: str) -> bool:
    return _has_title_term(title, INTERNSHIP_TITLE_WORDS)


# --- per-format mapping --------------------------------------------------------------------


def remotive_employment_type(job_type: object) -> EmploymentType:
    key = collapse_whitespace(job_type).casefold() if isinstance(job_type, str) else ""
    key = key.replace("-", "_").replace(" ", "_")
    return REMOTIVE_EMPLOYMENT_TYPES.get(key, EmploymentType.FULL_TIME)


def arbeitnow_employment_type(job_types: object) -> EmploymentType:
    values = job_types if isinstance(job_types, list) else [job_types]
    text = " ".join(value.casefold() for value in values if isinstance(value, str))
    if "intern" in text or "praktikum" in text:
        return EmploymentType.INTERNSHIP
    if "part" in text:
        return EmploymentType.PART_TIME
    if "contract" in text or "freelance" in text:
        return EmploymentType.CONTRACT
    return EmploymentType.FULL_TIME


def _map_remotive(raw: Mapping[str, object], _today: date) -> RawFields:
    description = _description(raw.get("description"))
    required = _tag_skills(raw.get("tags"))
    return {
        "external_id": _identifier(raw.get("id")),
        "title": _text(raw.get("title")),
        "company": _text(raw.get("company_name")),
        "location": _text(raw.get("candidate_required_location")) or DEFAULT_REMOTE_LOCATION,
        "work_mode": WorkMode.REMOTE,
        "employment_type": remotive_employment_type(raw.get("job_type")),
        "application_url": _url(raw.get("url")),
        "description": description,
        "required_skills": required,
        "preferred_skills": _description_skills(description, required),
    }


def _map_arbeitnow(raw: Mapping[str, object], _today: date) -> RawFields:
    description = _description(raw.get("description"))
    required = _tag_skills(raw.get("tags"))
    is_remote = raw.get("remote") is True
    location = _text(raw.get("location"))
    return {
        "external_id": _identifier(raw.get("slug")),
        "title": _text(raw.get("title")),
        "company": _text(raw.get("company_name")),
        "location": location or (DEFAULT_REMOTE_LOCATION if is_remote else None),
        "work_mode": WorkMode.REMOTE if is_remote else WorkMode.ONSITE,
        "employment_type": arbeitnow_employment_type(raw.get("job_types")),
        "application_url": _url(raw.get("url")),
        "description": description,
        "required_skills": required,
        "preferred_skills": _description_skills(description, required),
    }


def _resolve_deadline(raw: Mapping[str, object], today: date) -> object:
    """`deadline` wins; else `deadline_in_days` (an integer) relative to `today`."""
    deadline = raw.get("deadline")
    if deadline is not None:
        return deadline
    days = raw.get("deadline_in_days")
    if days is None:
        return None
    if isinstance(days, bool) or not isinstance(days, int):
        raise _ItemRejectedError("deadline_in_days: must be an integer")
    try:
        return today + timedelta(days=days)
    except OverflowError:
        raise _ItemRejectedError("deadline_in_days: out of range") from None


def _map_normalized(raw: Mapping[str, object], today: date) -> RawFields:
    fields: RawFields = {
        "external_id": _identifier(raw.get("external_id")),
        "application_url": _url(raw.get("application_url")),
        "description": _description(raw.get("description")),
    }
    for name in NORMALIZED_TEXT_FIELDS:
        value = raw.get(name)
        fields[name] = _text(value) if isinstance(value, str) else value
    for name in NORMALIZED_PASSTHROUGH_FIELDS:
        fields[name] = raw.get(name)
    fields["deadline"] = _resolve_deadline(raw, today)
    return fields


_MAPPERS: Mapping[RawFormat, Callable[[Mapping[str, object], date], RawFields]] = {
    RawFormat.REMOTIVE: _map_remotive,
    RawFormat.ARBEITNOW: _map_arbeitnow,
    RawFormat.NORMALIZED: _map_normalized,
}


def _apply_title_rules(fields: RawFields) -> None:
    """All formats: internship titles force the employment type; infer a missing level."""
    title = fields.get("title")
    if not isinstance(title, str):
        return
    if is_internship_title(title):
        fields["employment_type"] = EmploymentType.INTERNSHIP
    if fields.get("experience_level") is None:
        fields["experience_level"] = infer_experience_level(title)


def _describe(error: ValidationError) -> str:
    """`field: message` pairs without input values."""
    parts = []
    for item in error.errors(include_input=False, include_url=False, include_context=False):
        location = ".".join(str(part) for part in item["loc"]) or "item"
        parts.append(f"{location}: {item['msg']}")
    return "; ".join(parts)


def _truncate_reason(reason: str) -> str:
    if len(reason) <= REASON_MAX_LENGTH:
        return reason
    return reason[: REASON_MAX_LENGTH - 1] + "…"


def normalize_item(
    raw: object, raw_format: RawFormat, source: JobSource, today: date, index: int
) -> JobCreate | Rejection:
    """Map one raw item to a validated `JobCreate`, or say why it was rejected (R10.4)."""
    if not isinstance(raw, dict):
        return Rejection(index, "item: must be a JSON object")
    try:
        fields = _MAPPERS[raw_format](raw, today)
    except _ItemRejectedError as error:
        return Rejection(index, _truncate_reason(str(error)))
    _apply_title_rules(fields)
    values = {name: value for name, value in fields.items() if value is not None}
    values["source"] = source
    try:
        return JobCreate.model_validate(values)
    except ValidationError as error:
        return Rejection(index, _truncate_reason(_describe(error)))
