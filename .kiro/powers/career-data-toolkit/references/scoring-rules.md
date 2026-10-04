# Scoring rules (algorithm_version 1.0.0)

Verbatim copy of `.kiro/specs/internship-intelligence/design.md` §5 (§5.1 normalization, §5.2 skill sets, §5.3 factors/weights/rounding, §5.4 reason templates, §5.5 `match_explanation` shape, §5.6 edge cases). Only the heading levels are shifted by one. The implementation is `backend/app/services/matching/` (`normalization.py`, `skill_catalog.py`, `engine.py`, `types.py`).

Quick reference (weights sum to 100):

| # | Factor key | Weight |
|---|---|---|
| 1 | `required_skills` | 35 |
| 2 | `preferred_skills` | 10 |
| 3 | `role_similarity` | 15 |
| 4 | `experience` | 15 |
| 5 | `location` | 10 |
| 6 | `work_mode` | 5 |
| 7 | `education` | 5 |
| 8 | `projects` | 5 |

Score: `points = weight × ratio` with exact `Fraction`s, `total = Σ points`, `score = clamp(floor(total + 1/2), 0, 100)`.

Rule changes must bump `algorithm_version` and update `design.md` §5 and this file in the same commit. Regenerate this file from `design.md` rather than editing rules here by hand.

---

### 5. Matching engine (R3, R4)

Location: `app/services/matching/`. Public API:

```python
def normalize_skill(raw: str) -> str | None: ...
def normalize_skills(raws: Iterable[str]) -> frozenset[str]: ...
def display_skill(canonical: str) -> str: ...
def compute_match(profile: MatchProfile, job: MatchJob) -> MatchResult: ...

@dataclass(frozen=True)
class ProjectInput: name: str; technologies: tuple[str, ...]

@dataclass(frozen=True)
class MatchProfile:
    technical_skills: tuple[str, ...]          # raw; engine normalizes
    target_roles: tuple[str, ...]
    location: str | None
    preferred_locations: tuple[str, ...]
    preferred_work_modes: tuple[WorkMode, ...]
    experience_level: ExperienceLevel | None
    education_level: EducationLevel | None
    projects: tuple[ProjectInput, ...]

@dataclass(frozen=True)
class MatchJob:
    id: int; title: str; location: str; work_mode: WorkMode
    experience_level: ExperienceLevel | None
    min_education_level: EducationLevel | None
    required_skills: tuple[str, ...]; preferred_skills: tuple[str, ...]
```

`MatchResult` is a frozen dataclass mirrored 1:1 by the Pydantic `MatchExplanation` schema. The engine performs no I/O, reads no clock, uses no randomness, and accepts raw strings so normalization is part of the tested unit.

#### 5.1 Skill normalization

`normalize_skill(raw)`:
1. `unicodedata.normalize("NFKC", raw).casefold()`.
2. Replace any whitespace run with a single space.
3. Repeat until the string no longer changes: strip whitespace; strip leading/trailing characters in `EDGE_PUNCTUATION = ` `` ,;:|/\()[]{}"'` ``; strip one trailing `.`. (Internal `.`, `+`, `#` are preserved: `node.js`, `c++`, `c#`; a leading `.` is preserved: `.net`.) So `" React ,"`, `"( React )"` and `"React."` all become `react`.
4. Look up `ALIASES` (in `skill_catalog.py`); if present, replace with the canonical name. Every alias value is itself a canonical name that is a fixed point of steps 1–3 and not an alias key, so the function is idempotent: `normalize_skill(normalize_skill(x)) == normalize_skill(x)` whenever the inner result is not `None`.
5. Return `None` if empty or longer than 50 characters. The engine and ingestion ignore `None` results; profile input rejects them with 422 (§8.1, R1.3).

Tests: `test_normalize_skill_is_idempotent` (examples) plus a Hypothesis check in `tests/property/test_normalization_properties.py` that `normalize_skill(normalize_skill(x) or "") == normalize_skill(x)` for arbitrary text and for catalog/alias names wrapped in random edge punctuation and whitespace; a unit test asserts every `ALIASES` value is a fixed point.

`ALIASES` (minimum set; extend only by adding entries): `reactjs, react.js → react`; `js, ecmascript → javascript`; `ts → typescript`; `py, python3 → python`; `postgres, psql → postgresql`; `node, nodejs → node.js`; `ml → machine learning`; `dl → deep learning`; `k8s → kubernetes`; `amazon web services → aws`; `google cloud, google cloud platform → gcp`; `sklearn, scikit learn → scikit-learn`; `natural language processing → nlp`; `golang → go`; `c sharp → c#`; `cpp → c++`; `vuejs, vue.js → vue`; `nextjs → next.js`; `tailwind, tailwindcss → tailwind css`; `rest, rest api, restful, restful apis → rest apis`; `html5 → html`; `css3 → css`; `mongo → mongodb`; `gh actions, github action → github actions`; `ci/cd, cicd → ci/cd`.

`CATALOG` maps canonical → display name (`react → React`, `postgresql → PostgreSQL`, `node.js → Node.js`, `machine learning → Machine Learning`, …, ≥ 40 entries covering all seed skills). `display_skill(c)` returns `CATALOG[c]` if present, else each space-separated word with its first character upper-cased. The same catalog is used by resume extraction (§9.1) and documented in the custom Power's `references/scoring-rules.md`.

#### 5.2 Skill sets

- `S = normalize_skills(profile.technical_skills)` (a frozenset, so duplicates and order vanish — R3.7, R3.10).
- `R = normalize_skills(job.required_skills)`.
- `P = normalize_skills(job.preferred_skills) − R` (a skill listed in both counts only as required).

#### 5.3 Factors, weights and point rules

All ratios are `fractions.Fraction` values in [0, 1]; `points = weight × ratio` (exact). `total = Σ points` in the fixed factor order; `score = clamp(floor(total + 1/2), 0, 100)` (half-up, exact arithmetic, so no float drift; monotone in `total`). In the JSON response `points` and `ratio` are serialized as floats rounded to 2 and 4 decimals.

| # | key | label | weight | ratio rule |
|---|---|---|---|---|
| 1 | `required_skills` | Required skills | 35 | `R = ∅` → 1. Else `|R ∩ S| / |R|`. |
| 2 | `preferred_skills` | Preferred skills | 10 | `P = ∅` → 1. Else `|P ∩ S| / |P|`. |
| 3 | `role_similarity` | Role similarity | 15 | See role tokens below. `U = {t ∈ target_roles : tok(t) ≠ ∅}` (usable roles). `U = ∅` → 1/2 (neutral, no roles). Else `tok(title) = ∅` → 1/2 (neutral, no title terms). Else `max over t ∈ U of |tok(t) ∩ tok(title)| / |tok(t)|`. |
| 4 | `experience` | Experience | 15 | Ordinal `internship 0, entry 1, junior 2, mid 3, senior 4`. Either side unknown → 1/2. `gap = job − user`: `gap ≤ 0` → 1; `1` → 3/5; `2` → 1/5; `≥ 3` → 0. |
| 5 | `location` | Location | 10 | Job `remote` → 1. Candidates `C = preferred_locations ∪ {location}` (normalized, non-empty). `C = ∅` → 1/2. Any candidate's first segment = job's first segment → 1. Else any candidate's last segment = job's last segment → 1/2. Else 0. |
| 6 | `work_mode` | Work mode | 5 | Preferred modes empty → 1/2. Job mode ∈ preferred → 1. Job `hybrid` (not preferred) → 1/2. Else 0. |
| 7 | `education` | Education | 5 | Ordinal `high_school 0, diploma 1, bachelor 2, master 3, phd 4`. Job minimum null → 1. User unknown → 1/2. `user ≥ job` → 1; `user = job − 1` → 1/2; else 0. |
| 8 | `projects` | Project relevance | 5 | `J = R ∪ P`. `J = ∅` → 1/2. Projects are grouped by `casefold(strip(name))` (project groups, below). `k` = number of groups whose shared skills `⋃ normalize_skills(member.technologies) ∩ J ≠ ∅`: `k = 0` → 0; `k = 1` → 3/5; `k ≥ 2` → 1. |

Weights sum to 100. Only factors 1–2 depend on `S`, and both are non-decreasing in `S ∩ (R ∪ P)` and unaffected by skills outside `R ∪ P`; this is what makes P2 hold. Projects use project technologies, not `S`, so adding a technical skill never changes factor 8.

Role tokens `tok(s)`: casefold; replace `front-end|front end → frontend`, `back-end|back end → backend`, `full-stack|full stack → fullstack`; replace every character not in `[a-z0-9+#]` with a space; split; map `developer, dev, programmer → engineer`, `swe, sde → software, engineer` (expands to two tokens); drop stop tokens `intern, internship, trainee, junior, jr, senior, sr, lead, principal, staff, graduate, grad, new, entry, level, associate, i, ii, iii, the, and, of, for, a, an, to, in, at, with, remote, hybrid, onsite, m, f, d, w` and pure-digit tokens; result is a set. The "best role" for the reason and `detail` text is chosen from `U` among roles with the highest ratio: smallest `casefold(role)`, then smallest original string (Python `str` ordering). This is a total order on strings, so the choice is independent of input order (P5).

Project groups: group `profile.projects` by key `casefold(strip(name))`; skip projects whose stripped name is empty. A group's shared skills are the union over its members of `normalize_skills(technologies) ∩ J`; the group is relevant iff that union is non-empty; its display name is the lexicographically smallest original (stripped) `name` among members. Groups are ordered by key. This makes relevance, the shared skill and the displayed name independent of project order and of duplicates that differ only in case (P5).

Serialization: the engine keeps `points` and `ratio` as exact `Fraction`s, so R4.2 holds exactly inside the engine; JSON serializes `points` rounded to 2 decimals and `ratio` to 4, so in JSON `|points − weight × ratio| ≤ 0.01`.

Location segments: casefold, collapse whitespace, split on `,`, strip each segment, drop empty segments.

Clarifications (settled in task 4.1; `types.py`/`engine.py` implement exactly this):
- The level enums used by `MatchProfile`/`MatchJob` (`WorkMode`, `ExperienceLevel`, `EducationLevel`) are engine-local `StrEnum`s in `matching/types.py` with the same values as `app.schemas.common`, so the engine imports no schemas; services may pass either type (string equality/hash). A unit test pins the values together.
- "Job `remote`" (location factor) means `job.work_mode == remote`; the location string is not inspected.
- `tok(s)` and location segments start with `unicodedata.normalize("NFKC", s)` before casefolding (§5.6), and whitespace runs are collapsed first. The phrase replacements match whole words with one `-` or space between them (`\bfront(?:-| )end\b`, likewise `back end`, `full stack`).
- A job location with no segments (blank) never matches a candidate, so it scores 0 unless the job is remote.
- Location matching compares whole segments only: a single-segment candidate (`"Berlin"`) is both its first and last segment, so it gives 1 against `"Berlin, Germany"` (first segment) and `"Germany"` gives 1/2 (last segment). There is no substring or alias matching (`"Deutschland"` ≠ `"germany"`).
- Project group keys are exactly `casefold(strip(name))` (settled in task 4.2): no NFKC and no whitespace collapse, so `"My App"` and `"My  App"` are separate groups. The §5.6 NFKC rule covers skills, role tokens and location segments. Project technologies still go through `normalize_skills`, so aliases (`ReactJS → react`) count toward `J`.
- Helpers stay in `matching/engine.py` (the §3.2 module map lists no separate roles/locations/levels/projects modules); tests import them from there.
- `preferred_skills` with `P = ∅` scores 1 and emits no reason (the §5.4 table has no template for it).
- Rounding helpers: `round_half_up(x) = floor(x + 1/2)`; `to_rounded_float(x, places)` applies the same half-up rule to the exact `Fraction` (`x × 10^places`) before converting, so serialization never suffers float tie errors (e.g. `1/8 → 0.13`).

#### 5.4 Reasons

Every factor emits reasons into `positive_reasons` or `negative_reasons`. Skills use `display_skill`. Ordering: by factor order, then alphabetically by normalized skill within factors 1–2 (R4.6).

| Factor | Condition | Polarity | Template |
|---|---|---|---|
| required | each `s ∈ R ∩ S` | + | `{Skill} matches required skill` |
| required | each `s ∈ R − S` | − | `{Skill} experience is missing (required)` |
| required | `R = ∅` | + | `No required skills listed for this role` |
| preferred | each `s ∈ P ∩ S` | + | `{Skill} matches preferred skill` |
| preferred | each `s ∈ P − S` | − | `{Skill} is a preferred skill not in your profile` |
| role | ratio = 1 | + | `Job title matches your target role "{role}"` |
| role | 0 < ratio < 1 | + if ≥ 1/2 else − | `Job title partially matches your target role "{role}"` |
| role | ratio = 0 | − | `Job title does not match your target roles` |
| role | neutral, `U = ∅` | − | `Add target roles to your profile to improve role matching` |
| role | neutral, `tok(title) = ∅` | − | `Job title has no comparable role terms` |
| experience | ratio = 1 | + | `Your {user} experience meets the {job} level` |
| experience | 0 < ratio < 1 | − | `Role expects {job} level; your profile is {user}` |
| experience | ratio = 0 | − | `Role expects {job} level, well above your {user} level` |
| experience | neutral | − | `Experience level not specified` (profile or job missing) |
| location | remote | + | `Remote role, location-independent` |
| location | ratio = 1 | + | `{Job location} matches your location or preferred locations` |
| location | ratio = 1/2 (country) | + | `{Job location} is in a country you prefer` |
| location | ratio = 0 | − | `{Job location} is outside your preferred locations` |
| location | neutral | − | `Add a location or preferred locations to your profile` |
| work_mode | ratio = 1 | + | `{Mode} work matches your preference` |
| work_mode | hybrid partial | + | `Hybrid work partially matches your preference` |
| work_mode | ratio = 0 | − | `{Mode} work does not match your preferred work modes` |
| work_mode | neutral | − | `Add preferred work modes to your profile` |
| education | ratio = 1, no requirement | + | `No minimum education requirement` |
| education | ratio = 1 | + | `Your education meets the {job} requirement` |
| education | ratio = 1/2 | − | `Role prefers {job}; you are one level below` |
| education | ratio = 0 | − | `Role requires {job} education` |
| education | neutral | − | `Education level not specified in your profile` |
| projects | k ≥ 1 | + | `Project "{name}" uses {Skill}` (`{name}` = display name of the first relevant project group by key; `{Skill}` = its alphabetically first shared skill by normalized name); if k ≥ 2 append ` (+{k−1} more relevant projects)` |
| projects | k = 0 | − | `No projects demonstrate this role's skills` |
| projects | J = ∅ | − | `Role lists no skills to compare projects against` |

Level labels use human text (`full_time` is not used here; levels render as `internship`, `entry`, `junior`, `mid`, `senior`; education as `high school`, `diploma`, `bachelor's`, `master's`, `PhD`). The UI prefixes `+`/`−` (R4.7).

#### 5.5 `match_explanation` shape

```json
{
  "job_id": 12,
  "score": 87,
  "algorithm_version": "1.0.0",
  "factors": [
    {"key": "required_skills", "label": "Required skills", "weight": 35, "points": 26.25, "ratio": 0.75, "detail": "3 of 4 required skills matched"},
    {"key": "preferred_skills", "label": "Preferred skills", "weight": 10, "points": 10.0, "ratio": 1.0, "detail": "2 of 2 preferred skills matched"}
  ],
  "matched_required_skills": ["Python", "React", "SQL"],
  "missing_required_skills": ["Java"],
  "matched_preferred_skills": ["Docker", "Machine Learning"],
  "missing_preferred_skills": [],
  "positive_reasons": ["Python matches required skill", "React matches required skill"],
  "negative_reasons": ["Java experience is missing (required)"]
}
```

`factors` always has all eight entries in §5.3 order. `detail` templates: skills `"{m} of {n} required|preferred skills matched"` (or `"none listed"`), role `"best match: {role}"`/`"no target roles"`/`"no comparable title terms"`; experience `"{user} profile, {job} role"`/`"level not specified"`; location `"remote role"`/`"city or region matches"`/`"country matches"`/`"outside preferred locations"`/`"no locations in profile"`; work mode `"{Mode} is preferred"`/`"Hybrid is a partial match"`/`"{Mode} is not preferred"`/`"no preferred work modes"`; education `"no minimum requirement"`/`"meets {job}"`/`"one level below {job}"`/`"below {job}"`/`"education not specified"`; projects `"{k} of {groups} projects use the role's skills"`/`"no job skills to compare"`. Skill lists hold display names sorted by normalized name.

#### 5.6 Edge cases

Empty profile → all neutral/zero factors; score is still in range. Job with no skills → required/preferred full credit, projects neutral. Skills that normalize to `None` are ignored by the engine. Projects whose names collide after casefold form one group (§5.3), so they count once and the reason text does not depend on their order. Target roles made only of stop tokens (`"Intern"`, `"Senior"`) are not usable and never cause a division by zero. Unicode/full-width input is NFKC-normalized. `algorithm_version` is bumped on any rule change, and the Power's `scoring-rules.md` must be updated in the same commit.
