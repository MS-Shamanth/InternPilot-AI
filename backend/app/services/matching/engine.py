"""Deterministic match scoring: `compute_match` (design.md §5.2-§5.6, R3, R4).

Pure: no I/O, no clock, no randomness, no model/repository/schema imports. All arithmetic is
exact `Fraction` arithmetic; iteration over sets is always through `sorted(...)` so the result
never depends on input order or hash seeds (R3.10).
"""

import math
import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from fractions import Fraction
from types import MappingProxyType

from app.services.matching.normalization import display_skill, normalize_skills
from app.services.matching.types import (
    ALGORITHM_VERSION,
    FACTOR_SPECS,
    MAX_SCORE,
    MIN_SCORE,
    EducationLevel,
    ExperienceLevel,
    FactorResult,
    MatchJob,
    MatchProfile,
    MatchResult,
    ProjectInput,
    WorkMode,
)

ZERO = Fraction(0)
ONE = Fraction(1)
HALF = Fraction(1, 2)

EXPERIENCE_ORDINALS: Mapping[str, int] = MappingProxyType(
    {
        ExperienceLevel.INTERNSHIP: 0,
        ExperienceLevel.ENTRY: 1,
        ExperienceLevel.JUNIOR: 2,
        ExperienceLevel.MID: 3,
        ExperienceLevel.SENIOR: 4,
    }
)
# Ratio by `gap = job - user` for gap 1 and 2; gap <= 0 is full credit, gap >= 3 is zero.
EXPERIENCE_GAP_RATIOS: Mapping[int, Fraction] = MappingProxyType(
    {1: Fraction(3, 5), 2: Fraction(1, 5)}
)
EDUCATION_ORDINALS: Mapping[str, int] = MappingProxyType(
    {
        EducationLevel.HIGH_SCHOOL: 0,
        EducationLevel.DIPLOMA: 1,
        EducationLevel.BACHELOR: 2,
        EducationLevel.MASTER: 3,
        EducationLevel.PHD: 4,
    }
)
EDUCATION_LABELS: Mapping[str, str] = MappingProxyType(
    {
        EducationLevel.HIGH_SCHOOL: "high school",
        EducationLevel.DIPLOMA: "diploma",
        EducationLevel.BACHELOR: "bachelor's",
        EducationLevel.MASTER: "master's",
        EducationLevel.PHD: "PhD",
    }
)
WORK_MODE_LABELS: Mapping[str, str] = MappingProxyType(
    {WorkMode.REMOTE: "Remote", WorkMode.HYBRID: "Hybrid", WorkMode.ONSITE: "Onsite"}
)
SINGLE_PROJECT_RATIO = Fraction(3, 5)

ROLE_PHRASES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bfront(?:-| )end\b"), "frontend"),
    (re.compile(r"\bback(?:-| )end\b"), "backend"),
    (re.compile(r"\bfull(?:-| )stack\b"), "fullstack"),
)
ROLE_NON_TOKEN = re.compile(r"[^a-z0-9+#]")
ROLE_TOKEN_MAP: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "developer": ("engineer",),
        "dev": ("engineer",),
        "programmer": ("engineer",),
        "swe": ("software", "engineer"),
        "sde": ("software", "engineer"),
    }
)
ROLE_STOP_TOKENS = frozenset(
    (
        "intern internship trainee junior jr senior sr lead principal staff graduate grad new"
        " entry level associate i ii iii the and of for a an to in at with remote hybrid onsite"
        " m f d w"
    ).split()
)
_WHITESPACE_RUN = re.compile(r"\s+")


@dataclass(frozen=True)
class _Outcome:
    """A factor's ratio, `detail` text and the reasons it emits."""

    ratio: Fraction
    detail: str
    positive: tuple[str, ...] = ()
    negative: tuple[str, ...] = ()


@dataclass(frozen=True)
class _ProjectGroup:
    key: str
    display_name: str
    shared_skills: frozenset[str]


# ---------- rounding ----------


def round_half_up(value: Fraction) -> int:
    """Nearest integer, ties toward +infinity: `floor(value + 1/2)` (exact)."""
    return math.floor(value + HALF)


def clamp_score(value: int) -> int:
    return max(MIN_SCORE, min(MAX_SCORE, value))


def to_rounded_float(value: Fraction, places: int) -> float:
    """`value` rounded half-up to `places` decimals, for JSON (`points` 2, `ratio` 4)."""
    scale = 10**places
    return round_half_up(value * scale) / scale


# ---------- text helpers ----------


def _fold(text: str) -> str:
    """NFKC + casefold + collapse whitespace runs to one space."""
    return _WHITESPACE_RUN.sub(" ", unicodedata.normalize("NFKC", text).casefold())


def role_tokens(text: str) -> frozenset[str]:
    """`tok(s)` from design.md §5.3."""
    folded = _fold(text)
    for pattern, replacement in ROLE_PHRASES:
        folded = pattern.sub(replacement, folded)
    tokens: set[str] = set()
    for raw in ROLE_NON_TOKEN.sub(" ", folded).split():
        for token in ROLE_TOKEN_MAP.get(raw, (raw,)):
            if token not in ROLE_STOP_TOKENS and not token.isdigit():
                tokens.add(token)
    return frozenset(tokens)


def location_segments(text: str) -> tuple[str, ...]:
    """Casefolded, whitespace-collapsed, comma-separated non-empty segments."""
    return tuple(
        segment for segment in (part.strip() for part in _fold(text).split(",")) if segment
    )


def _sorted_display(skills: Iterable[str]) -> tuple[str, ...]:
    return tuple(display_skill(skill) for skill in sorted(skills))


# ---------- factors ----------


def _required_factor(required: frozenset[str], skills: frozenset[str]) -> _Outcome:
    if not required:
        return _Outcome(ONE, "none listed", positive=("No required skills listed for this role",))
    matched = sorted(required & skills)
    missing = sorted(required - skills)
    return _Outcome(
        Fraction(len(matched), len(required)),
        f"{len(matched)} of {len(required)} required skills matched",
        positive=tuple(f"{display_skill(s)} matches required skill" for s in matched),
        negative=tuple(f"{display_skill(s)} experience is missing (required)" for s in missing),
    )


def _preferred_factor(preferred: frozenset[str], skills: frozenset[str]) -> _Outcome:
    if not preferred:
        return _Outcome(ONE, "none listed")
    matched = sorted(preferred & skills)
    missing = sorted(preferred - skills)
    return _Outcome(
        Fraction(len(matched), len(preferred)),
        f"{len(matched)} of {len(preferred)} preferred skills matched",
        positive=tuple(f"{display_skill(s)} matches preferred skill" for s in matched),
        negative=tuple(
            f"{display_skill(s)} is a preferred skill not in your profile" for s in missing
        ),
    )


def _role_factor(target_roles: tuple[str, ...], title: str) -> _Outcome:
    usable = {role: tokens for role in target_roles if (tokens := role_tokens(role))}
    if not usable:
        return _Outcome(
            HALF,
            "no target roles",
            negative=("Add target roles to your profile to improve role matching",),
        )
    title_tokens = role_tokens(title)
    if not title_tokens:
        return _Outcome(
            HALF, "no comparable title terms", negative=("Job title has no comparable role terms",)
        )
    ratios = {
        role: Fraction(len(tokens & title_tokens), len(tokens)) for role, tokens in usable.items()
    }
    ratio = max(ratios.values())
    best_role = min((role for role, value in ratios.items() if value == ratio), key=_role_order)
    detail = f"best match: {best_role}"
    if ratio == ONE:
        return _Outcome(
            ratio, detail, positive=(f'Job title matches your target role "{best_role}"',)
        )
    if ratio == ZERO:
        return _Outcome(ratio, detail, negative=("Job title does not match your target roles",))
    reason = f'Job title partially matches your target role "{best_role}"'
    if ratio >= HALF:
        return _Outcome(ratio, detail, positive=(reason,))
    return _Outcome(ratio, detail, negative=(reason,))


def _role_order(role: str) -> tuple[str, str]:
    return (role.casefold(), role)


def _experience_factor(user: ExperienceLevel | None, job: ExperienceLevel | None) -> _Outcome:
    if user is None or job is None:
        return _Outcome(HALF, "level not specified", negative=("Experience level not specified",))
    gap = EXPERIENCE_ORDINALS[job] - EXPERIENCE_ORDINALS[user]
    user_label, job_label = str(user), str(job)
    detail = f"{user_label} profile, {job_label} role"
    if gap <= 0:
        return _Outcome(
            ONE, detail, positive=(f"Your {user_label} experience meets the {job_label} level",)
        )
    ratio = EXPERIENCE_GAP_RATIOS.get(gap, ZERO)
    if ratio == ZERO:
        return _Outcome(
            ratio,
            detail,
            negative=(f"Role expects {job_label} level, well above your {user_label} level",),
        )
    return _Outcome(
        ratio, detail, negative=(f"Role expects {job_label} level; your profile is {user_label}",)
    )


def _location_factor(profile: MatchProfile, job: MatchJob) -> _Outcome:
    if job.work_mode == WorkMode.REMOTE:
        return _Outcome(ONE, "remote role", positive=("Remote role, location-independent",))
    raw_candidates = (*profile.preferred_locations, profile.location or "")
    candidates = {segments for raw in raw_candidates if (segments := location_segments(raw))}
    if not candidates:
        return _Outcome(
            HALF,
            "no locations in profile",
            negative=("Add a location or preferred locations to your profile",),
        )
    job_location = job.location.strip()
    job_segments = location_segments(job.location)
    if job_segments and any(c[0] == job_segments[0] for c in candidates):
        return _Outcome(
            ONE,
            "city or region matches",
            positive=(f"{job_location} matches your location or preferred locations",),
        )
    if job_segments and any(c[-1] == job_segments[-1] for c in candidates):
        return _Outcome(
            HALF, "country matches", positive=(f"{job_location} is in a country you prefer",)
        )
    return _Outcome(
        ZERO,
        "outside preferred locations",
        negative=(f"{job_location} is outside your preferred locations",),
    )


def _work_mode_factor(preferred: tuple[WorkMode, ...], mode: WorkMode) -> _Outcome:
    label = WORK_MODE_LABELS[mode]
    if not preferred:
        return _Outcome(
            HALF, "no preferred work modes", negative=("Add preferred work modes to your profile",)
        )
    if mode in preferred:
        return _Outcome(
            ONE, f"{label} is preferred", positive=(f"{label} work matches your preference",)
        )
    if mode == WorkMode.HYBRID:
        return _Outcome(
            HALF,
            "Hybrid is a partial match",
            positive=("Hybrid work partially matches your preference",),
        )
    return _Outcome(
        ZERO,
        f"{label} is not preferred",
        negative=(f"{label} work does not match your preferred work modes",),
    )


def _education_factor(user: EducationLevel | None, job: EducationLevel | None) -> _Outcome:
    if job is None:
        return _Outcome(
            ONE, "no minimum requirement", positive=("No minimum education requirement",)
        )
    if user is None:
        return _Outcome(
            HALF,
            "education not specified",
            negative=("Education level not specified in your profile",),
        )
    job_label = EDUCATION_LABELS[job]
    difference = EDUCATION_ORDINALS[user] - EDUCATION_ORDINALS[job]
    if difference >= 0:
        return _Outcome(
            ONE,
            f"meets {job_label}",
            positive=(f"Your education meets the {job_label} requirement",),
        )
    if difference == -1:
        return _Outcome(
            HALF,
            f"one level below {job_label}",
            negative=(f"Role prefers {job_label}; you are one level below",),
        )
    return _Outcome(ZERO, f"below {job_label}", negative=(f"Role requires {job_label} education",))


def _project_groups(
    projects: tuple[ProjectInput, ...], job_skills: frozenset[str]
) -> tuple[_ProjectGroup, ...]:
    """Projects grouped by `casefold(strip(name))`, ordered by key (design.md §5.3)."""
    names: dict[str, set[str]] = {}
    skills: dict[str, set[str]] = {}
    for project in projects:
        name = project.name.strip()
        if not name:
            continue
        key = name.casefold()
        names.setdefault(key, set()).add(name)
        skills.setdefault(key, set()).update(normalize_skills(project.technologies) & job_skills)
    return tuple(
        _ProjectGroup(key, min(names[key]), frozenset(skills[key])) for key in sorted(names)
    )


def _projects_factor(projects: tuple[ProjectInput, ...], job_skills: frozenset[str]) -> _Outcome:
    if not job_skills:
        return _Outcome(
            HALF,
            "no job skills to compare",
            negative=("Role lists no skills to compare projects against",),
        )
    groups = _project_groups(projects, job_skills)
    relevant = [group for group in groups if group.shared_skills]
    detail = f"{len(relevant)} of {len(groups)} projects use the role's skills"
    if not relevant:
        return _Outcome(ZERO, detail, negative=("No projects demonstrate this role's skills",))
    first = relevant[0]
    reason = f'Project "{first.display_name}" uses {display_skill(min(first.shared_skills))}'
    if len(relevant) >= 2:
        reason += f" (+{len(relevant) - 1} more relevant projects)"
    ratio = ONE if len(relevant) >= 2 else SINGLE_PROJECT_RATIO
    return _Outcome(ratio, detail, positive=(reason,))


# ---------- entry point ----------


def compute_match(profile: MatchProfile, job: MatchJob) -> MatchResult:
    """Score `profile` against `job` (0-100) with the full explanation (design.md §5)."""
    skills = normalize_skills(profile.technical_skills)
    required = normalize_skills(job.required_skills)
    preferred = normalize_skills(job.preferred_skills) - required
    outcomes = (
        _required_factor(required, skills),
        _preferred_factor(preferred, skills),
        _role_factor(profile.target_roles, job.title),
        _experience_factor(profile.experience_level, job.experience_level),
        _location_factor(profile, job),
        _work_mode_factor(profile.preferred_work_modes, job.work_mode),
        _education_factor(profile.education_level, job.min_education_level),
        _projects_factor(profile.projects, required | preferred),
    )
    factors = tuple(
        FactorResult(
            key=spec.key,
            label=spec.label,
            weight=spec.weight,
            ratio=outcome.ratio,
            points=spec.weight * outcome.ratio,
            detail=outcome.detail,
        )
        for spec, outcome in zip(FACTOR_SPECS, outcomes, strict=True)
    )
    total = sum((factor.points for factor in factors), ZERO)
    return MatchResult(
        job_id=job.id,
        score=clamp_score(round_half_up(total)),
        algorithm_version=ALGORITHM_VERSION,
        factors=factors,
        matched_required_skills=_sorted_display(required & skills),
        missing_required_skills=_sorted_display(required - skills),
        matched_preferred_skills=_sorted_display(preferred & skills),
        missing_preferred_skills=_sorted_display(preferred - skills),
        positive_reasons=tuple(reason for outcome in outcomes for reason in outcome.positive),
        negative_reasons=tuple(reason for outcome in outcomes for reason in outcome.negative),
    )
