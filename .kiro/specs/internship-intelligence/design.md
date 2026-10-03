# Design: Internship Intelligence (InternPilot AI)

## 1. Overview

InternPilot AI is a three-tier web application: a React + TypeScript single-page app talks REST/JSON to a FastAPI backend, which persists to PostgreSQL through SQLAlchemy 2 repositories. The heart of the system is a pure, deterministic matching engine (`app/services/matching/`) that turns a (profile, job) pair into a 0–100 score and a `match_explanation`. Everything else — job lists, recommendations, dashboard, resume analysis — calls that one engine, so a pair never shows two scores (R3.12). Job ingestion pulls from allow-listed public APIs, captured MCP payloads or local fixtures, normalizes and dedupes, and always has an offline fallback (R10). Interview prep is template-driven behind a provider interface, with an optional OpenAI-compatible LLM enrichment that is off by default (R9, R15). A single seeded demo user is resolved by a request dependency; this is explicitly not production auth (R13).

Every section below names the requirement IDs it satisfies. Where alternatives existed, the chosen option is stated with its reason; the implementer should not re-open these decisions.

## 2. Technology stack (locked)

| Layer | Choice | Version line (pin exact patch at install) |
|---|---|---|
| Frontend runtime | Node 22, Vite 5, React 18, TypeScript 5 (`strict`) | vite 5.4.x, react 18.3.x, typescript 5.6.x |
| Styling | Tailwind CSS 3 with design tokens in `tailwind.config.ts` | tailwindcss 3.4.x, postcss 8, autoprefixer 10 |
| Routing | React Router 6 (data-less `BrowserRouter` + `Routes`) | react-router-dom 6.28.x |
| Server state | TanStack Query 5 | @tanstack/react-query 5.x |
| Charts | Recharts 2 | recharts 2.13.x |
| Frontend tests | Vitest 2 + Testing Library + jsdom | vitest 2.1.x, @testing-library/react 16.x, @testing-library/user-event 14.x, jsdom 25.x |
| Frontend quality | ESLint 9 (flat config, typescript-eslint, react-hooks, jsx-a11y), Prettier 3 | |
| Backend | Python 3.12, FastAPI, Uvicorn, Pydantic v2, pydantic-settings, email-validator | fastapi 0.115.x, pydantic 2.9.x, uvicorn 0.32.x |
| Persistence | SQLAlchemy 2 (typed `Mapped[]` ORM), Alembic, psycopg 3 (binary) | sqlalchemy 2.0.x, alembic 1.14.x, psycopg[binary] 3.2.x |
| HTTP client | httpx (ingestion, optional LLM) | httpx 0.27.x |
| Backend tests | pytest, Hypothesis, pytest-cov | pytest 8.3.x, hypothesis 6.x |
| Backend quality | Ruff (lint + format), Black (style check) | ruff 0.7.x, black 24.x |
| Database | PostgreSQL 16 (Docker); SQLite for the default test run | postgres:16-alpine |
| Infra | Docker, Docker Compose v2, nginx (static frontend) | nginx:1.27-alpine |

Decisions:
- **TanStack Query over hand-rolled hooks.** Cross-page invalidation (an application move must refresh dashboard, jobs and recommendations) is the main client-side complexity; TanStack Query solves it with one well-maintained dependency and removes custom cache code.
- **No drag-and-drop library.** Native HTML5 drag events plus a keyboard "Move to" menu meet R5.11 and R14.4 without extra dependencies.
- **Ruff format + Black.** The PostFileSave hook runs `ruff format` and `ruff check --fix`; `black --check` runs in the lint gate. Both are configured with line length 100 and Ruff's formatter targets Black style, so they agree.
- **No mypy.** Type safety comes from typed SQLAlchemy/Pydantic models, Ruff's annotation rules (`ANN`) and strict TypeScript; this keeps the toolchain to the brief's list.

## 3. Architecture

### 3.1 Backend layers

```
app/api/routes/*.py      HTTP only: parse/validate (schemas), call one service method, map result → response schema
app/services/**          Business rules, orchestration, transactions; pure engines live here
app/repositories/*.py    All SQLAlchemy queries; return ORM objects or simple DTOs; no business rules
app/models/*.py          SQLAlchemy ORM models + constraints
app/schemas/*.py         Pydantic request/response models (API contract)
app/core/*.py            config, database session, errors, logging, request-id middleware, dependencies (current user, clock)
```

Dependency rules (enforced by review and the architect agent): `api → services → repositories → models`; `services` may import `schemas` for input/output types; `repositories` never import `services` or `api`; the matching engine (`services/matching/engine.py`) imports nothing from models, repositories, FastAPI or the network — it works on frozen dataclasses only. Route handlers contain no `if` on business state.

### 3.2 Backend module map

```
backend/
  pyproject.toml                       ruff/black/pytest/coverage config
  requirements.txt, requirements-dev.txt
  alembic.ini, alembic/env.py, alembic/versions/0001_initial.py
  app/main.py                          create_app(): middleware, routers, exception handlers
  app/cli.py                           `python -m app.cli seed|ingest`
  app/core/config.py                   Settings (pydantic-settings)
  app/core/database.py                 engine/session factory, get_session dependency
  app/core/errors.py                   AppError hierarchy + exception handlers
  app/core/logging.py                  logging setup, request-id context var
  app/core/middleware.py               RequestIdMiddleware, BodySizeLimitMiddleware
  app/core/deps.py                     get_current_user, get_clock, service factories
  app/core/clock.py                    Clock protocol, SystemClock, FixedClock (tests)
  app/models/{base,user,skill,job,application,activity}.py
  app/schemas/{common,profile,job,application,match,dashboard,resume,interview,ingest}.py
  app/repositories/{user,skill,job,job_state,application,activity}_repository.py
  app/services/matching/{types,skill_catalog,normalization,engine}.py
  app/services/{profile,job,application,dashboard,recommendation,resume,seed}_service.py
  app/services/application_status.py   pure state machine
  app/services/interview/{provider,templates,template_provider,llm_provider,service}.py
  app/services/ingestion/{sources,normalizers,service}.py
  app/api/router.py, app/api/routes/{health,profile,jobs,applications,dashboard,recommendations,resume,interview}.py
  tests/{unit,integration,api,property}/, tests/conftest.py
```

### 3.3 Data flow (job list example)

`GET /api/jobs?q=react&sort=match_score` → route validates `JobListParams` → `JobService.list_jobs(user, params)` → `JobRepository.search(filters)` (SQL filters only) + `JobStateRepository.for_user` + `ApplicationRepository.status_by_job` → service builds `MatchProfile` once and `MatchJob` per job → `engine.compute_match` per job → applies `min_score`, sorts, paginates in memory → returns `Page[JobSummary]`.

Decision: **score in the service, paginate in memory.** Scores depend on the live profile (R1.6) so they cannot be precomputed in SQL without a cache-invalidation scheme. Computing ~1,000 matches is well under NFR1 (engine < 1 ms each). SQL still does text/enum filtering, so the in-memory set is only filtered candidates. If the dataset ever exceeds ~5,000 jobs, a score cache keyed by (user, job, profile `updated_at`) is the documented next step; not built now.

### 3.4 Frontend layers

`pages/*` compose `components/*` and call hooks from `hooks/*`; hooks wrap TanStack Query around typed functions in `api/*`; `api/client.ts` is the only place that calls `fetch`. Components receive data and callbacks via props and contain no scoring, transition or metric logic (R14.6). Allowed status moves come from `GET /api/applications/meta`.

## 4. Data model

All tables use integer surrogate PKs, `created_at`/`updated_at` as `DateTime(timezone=True)` in UTC (server default `now()`, `onupdate`). JSON columns use `sa.JSON().with_variant(JSONB, "postgresql")` so SQLite tests run unchanged (NFR2). Enum-like columns are `String` + `CheckConstraint` (portable, migration-friendly) rather than native PG enums.

### 4.1 Tables

**users**
| Column | Type | Notes |
|---|---|---|
| id | int PK | |
| name | varchar(100) not null | |
| email | varchar(254) not null **unique** | stored lowercase |
| location | varchar(120) null | |
| experience_level | varchar(16) null | check in `internship, entry, junior, mid, senior` |
| education_level | varchar(16) null | check in `high_school, diploma, bachelor, master, phd` |
| education | JSON not null default `[]` | list of `{institution, degree, field, start_year, end_year}` |
| target_roles | JSON not null default `[]` | list[str] |
| preferred_locations | JSON not null default `[]` | list[str] |
| preferred_work_modes | JSON not null default `[]` | list of `remote/hybrid/onsite` |
| soft_skills | JSON not null default `[]` | list[str] |
| projects | JSON not null default `[]` | list of `{name, description, technologies[], url}` |
| certifications | JSON not null default `[]` | list of `{name, issuer, year}` |
| resume_text | text not null default `''` | |
| github_url, portfolio_url, linkedin_url | varchar(300) null | |
| created_at, updated_at | timestamptz | |

Decision: list-shaped profile fields are JSON columns, not child tables. They are always read and written as a whole with the profile (PUT is full replace), are never queried relationally, and JSON keeps the schema portable. Technical skills are the exception — they go through the shared catalog (`user_skills`) because jobs reference the same skills (R1.3).

**skills**: `id`, `name varchar(80)` (display), `normalized_name varchar(80) unique not null`.

**user_skills**: `user_id FK users ON DELETE CASCADE`, `skill_id FK skills ON DELETE CASCADE`, PK(`user_id`, `skill_id`). The composite PK makes duplicate skills impossible at the DB level.

**jobs**
| Column | Type | Notes |
|---|---|---|
| id | int PK | |
| source | varchar(32) not null | `seed`, `fixture`, `remotive`, `arbeitnow`, `payload` |
| external_id | varchar(128) not null | |
| dedupe_fingerprint | char(64) not null **unique** | sha256 hex, §11.4 |
| title, company | varchar(200) not null | |
| location | varchar(200) not null | |
| employment_type | varchar(16) not null | check in `internship, full_time, part_time, contract` |
| work_mode | varchar(8) not null | check in `remote, hybrid, onsite` |
| experience_level | varchar(16) null | same check as users |
| min_education_level | varchar(16) null | same check as users |
| description | text not null | ≤ 20,000 chars after normalization |
| salary_min, salary_max | int null | check `salary_min <= salary_max` when both set, both ≥ 0 |
| salary_currency | char(3) null | |
| salary_period | varchar(8) null | check in `year, month, hour` |
| application_url | varchar(500) not null | |
| deadline | date null | |
| discovered_at | timestamptz not null | |
| created_at, updated_at | timestamptz | |

Constraints: `UNIQUE(source, external_id)` (`uq_jobs_source_external_id`), `UNIQUE(dedupe_fingerprint)`. Indexes: `ix_jobs_discovered_at`, `ix_jobs_deadline`, `ix_jobs_employment_type`, `ix_jobs_work_mode`.

**job_skills**: `job_id FK jobs ON DELETE CASCADE`, `skill_id FK skills`, `is_required bool not null`, PK(`job_id`, `skill_id`). A skill listed as both required and preferred is stored once with `is_required=true` (§5.2).

**user_job_states**: `user_id FK`, `job_id FK`, `is_bookmarked bool not null default false`, `is_hidden bool not null default false`, `updated_at`, PK(`user_id`, `job_id`). Rows are created lazily on first bookmark/hide.

**applications**
| Column | Type | Notes |
|---|---|---|
| id | int PK | |
| user_id | FK users ON DELETE CASCADE | |
| job_id | FK jobs ON DELETE CASCADE | |
| status | varchar(16) not null | `CHECK (status IN ('Saved','Interested','Applied','Assessment','Interview','Rejected','Offer','Withdrawn'))` named `ck_applications_status` |
| applied_at | date null | |
| deadline | date null | overrides job deadline for this user |
| interview_date | timestamptz null | |
| recruiter_name | varchar(120) null | |
| recruiter_email | varchar(254) null | |
| notes | text not null default `''` | ≤ 5,000 |
| outcome | varchar(500) null | free text |
| created_at, updated_at | timestamptz | |

Constraint `UNIQUE(user_id, job_id)` (`uq_applications_user_job`). Index `ix_applications_user_status`.

**activity_events**: `id`, `user_id FK`, `type varchar(40)` (`application_created`, `status_changed`, `application_updated`, `application_deleted`, `job_bookmarked`, `job_hidden`, `profile_updated`, `jobs_ingested`), `job_id FK null ON DELETE SET NULL`, `application_id int null` (no FK so history survives deletes), `message varchar(300)`, `created_at`. Index `ix_activity_user_created`. Added beyond the brief's table list because "recent activity" (R6.1) needs a durable source; deriving it from `updated_at` would lose deletes and intermediate moves.

### 4.2 Invariant ownership

| Invariant | Owner | Why |
|---|---|---|
| Status ∈ 8 values | Pydantic `ApplicationStatus` enum (API) + `ck_applications_status` (DB) | Rejects bad input early; DB is the last line for any code path (seed, scripts). |
| Allowed transitions | `application_status.transition()` used by `ApplicationService` | Pure, unit/property-testable; DB cannot express it. |
| One application per (user, job) | `uq_applications_user_job`; service pre-checks for a friendly 409 | Race-safe at DB, friendly at service. |
| No duplicate skills per user/job | composite PKs + normalization in `SkillRepository.get_or_create_many` | |
| Job dedupe | `uq_jobs_source_external_id`, unique fingerprint; ingestion service decides update/skip | |
| Score bounds/determinism | `matching.engine` | Single pure implementation (R3.12). |
| Per-user scoping | Repositories take `user_id` explicitly on every per-user query | Prevents cross-user leakage by construction. |

### 4.3 Migrations

One initial Alembic revision `0001_initial` creates all tables, constraints and indexes, written by hand (not autogenerate-only) so constraint names are stable. `alembic/env.py` reads `DATABASE_URL` from `Settings`. Downgrade drops all tables.

## 5. Matching engine (R3, R4)

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

### 5.1 Skill normalization

`normalize_skill(raw)`:
1. `unicodedata.normalize("NFKC", raw).casefold()`.
2. Replace any whitespace run with a single space; strip.
3. Strip leading/trailing characters in `` ,;:|/\()[]{}"'` `` and a trailing `.` (internal `.`, `+`, `#` are preserved: `node.js`, `c++`, `c#`, `.net`).
4. Look up `ALIASES` (in `skill_catalog.py`); if present, replace with the canonical name.
5. Return `None` if empty or longer than 50 characters (ignored, never an error).

`ALIASES` (minimum set; extend only by adding entries): `reactjs, react.js → react`; `js, ecmascript → javascript`; `ts → typescript`; `py, python3 → python`; `postgres, psql → postgresql`; `node, nodejs → node.js`; `ml → machine learning`; `dl → deep learning`; `k8s → kubernetes`; `amazon web services → aws`; `google cloud, google cloud platform → gcp`; `sklearn, scikit learn → scikit-learn`; `natural language processing → nlp`; `golang → go`; `c sharp → c#`; `cpp → c++`; `vuejs, vue.js → vue`; `nextjs → next.js`; `tailwind, tailwindcss → tailwind css`; `rest, rest api, restful, restful apis → rest apis`; `html5 → html`; `css3 → css`; `mongo → mongodb`; `gh actions, github action → github actions`; `ci/cd, cicd → ci/cd`.

`CATALOG` maps canonical → display name (`react → React`, `postgresql → PostgreSQL`, `node.js → Node.js`, `machine learning → Machine Learning`, …, ≥ 40 entries covering all seed skills). `display_skill(c)` returns `CATALOG[c]` if present, else each space-separated word with its first character upper-cased. The same catalog is used by resume extraction (§9.1) and documented in the custom Power's `references/scoring-rules.md`.

### 5.2 Skill sets

- `S = normalize_skills(profile.technical_skills)` (a frozenset, so duplicates and order vanish — R3.7, R3.10).
- `R = normalize_skills(job.required_skills)`.
- `P = normalize_skills(job.preferred_skills) − R` (a skill listed in both counts only as required).

### 5.3 Factors, weights and point rules

All ratios are `fractions.Fraction` values in [0, 1]; `points = weight × ratio` (exact). `total = Σ points` in the fixed factor order; `score = clamp(floor(total + 1/2), 0, 100)` (half-up, exact arithmetic, so no float drift; monotone in `total`). In the JSON response `points` and `ratio` are serialized as floats rounded to 2 and 4 decimals.

| # | key | label | weight | ratio rule |
|---|---|---|---|---|
| 1 | `required_skills` | Required skills | 35 | `R = ∅` → 1. Else `|R ∩ S| / |R|`. |
| 2 | `preferred_skills` | Preferred skills | 10 | `P = ∅` → 1. Else `|P ∩ S| / |P|`. |
| 3 | `role_similarity` | Role similarity | 15 | See role tokens below. No usable target roles or empty title tokens → 1/2. Else `max over target roles t of |tok(t) ∩ tok(title)| / |tok(t)|`. |
| 4 | `experience` | Experience | 15 | Ordinal `internship 0, entry 1, junior 2, mid 3, senior 4`. Either side unknown → 1/2. `gap = job − user`: `gap ≤ 0` → 1; `1` → 3/5; `2` → 1/5; `≥ 3` → 0. |
| 5 | `location` | Location | 10 | Job `remote` → 1. Candidates `C = preferred_locations ∪ {location}` (normalized, non-empty). `C = ∅` → 1/2. Any candidate's first segment = job's first segment → 1. Else any candidate's last segment = job's last segment → 1/2. Else 0. |
| 6 | `work_mode` | Work mode | 5 | Preferred modes empty → 1/2. Job mode ∈ preferred → 1. Job `hybrid` (not preferred) → 1/2. Else 0. |
| 7 | `education` | Education | 5 | Ordinal `high_school 0, diploma 1, bachelor 2, master 3, phd 4`. Job minimum null → 1. User unknown → 1/2. `user ≥ job` → 1; `user = job − 1` → 1/2; else 0. |
| 8 | `projects` | Project relevance | 5 | `J = R ∪ P`. `J = ∅` → 1/2. `k` = number of distinct (casefolded name) projects with `normalize_skills(technologies) ∩ J ≠ ∅`: `k = 0` → 0; `k = 1` → 3/5; `k ≥ 2` → 1. |

Weights sum to 100. Only factors 1–2 depend on `S`, and both are non-decreasing in `S ∩ (R ∪ P)` and unaffected by skills outside `R ∪ P`; this is what makes P2 hold. Projects use project technologies, not `S`, so adding a technical skill never changes factor 8.

Role tokens `tok(s)`: casefold; replace `front-end|front end → frontend`, `back-end|back end → backend`, `full-stack|full stack → fullstack`; replace every character not in `[a-z0-9+#]` with a space; split; map `developer, dev, programmer → engineer`, `swe, sde → software, engineer` (expands to two tokens); drop stop tokens `intern, internship, trainee, junior, jr, senior, sr, lead, principal, staff, graduate, grad, new, entry, level, associate, i, ii, iii, the, and, of, for, a, an, to, in, at, with, remote, hybrid, onsite, m, f, d, w` and pure-digit tokens; result is a set. The "best role" for the reason text is the role with the highest ratio, ties broken by the lexicographically smallest casefolded role string (order-independent).

Location segments: casefold, collapse whitespace, split on `,`, strip each segment, drop empty segments.

### 5.4 Reasons

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
| role | neutral | − | `Add target roles to your profile to improve role matching` |
| experience | ratio = 1 | + | `Your {user} experience meets the {job} level` |
| experience | 0 < ratio < 1 | − | `Role expects {job} level; your profile is {user}` |
| experience | ratio = 0 | − | `Role expects {job} level, well above your {user} level` |
| experience | neutral | − | `Experience level not specified` (profile or job missing) |
| location | remote | + | `Remote role, location-independent` |
| location | ratio = 1 | + | `{Job location} is one of your preferred locations` |
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
| projects | k ≥ 1 | + | `Project "{name}" uses {Skill}` (first relevant project by casefolded name, first shared skill alphabetically); if k ≥ 2 append ` (+{k−1} more relevant projects)` |
| projects | k = 0 | − | `No projects demonstrate this role's skills` |
| projects | J = ∅ | − | `Role lists no skills to compare projects against` |

Level labels use human text (`full_time` is not used here; levels render as `internship`, `entry`, `junior`, `mid`, `senior`; education as `high school`, `diploma`, `bachelor's`, `master's`, `PhD`). The UI prefixes `+`/`−` (R4.7).

### 5.5 `match_explanation` shape

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

`factors` always has all eight entries in §5.3 order. `detail` templates: skills `"{m} of {n} required|preferred skills matched"` (or `"none listed"`), role `"best match: {role}"`/`"no target roles"`, others a short human summary. Skill lists hold display names sorted by normalized name.

### 5.6 Edge cases

Empty profile → all neutral/zero factors; score is still in range. Job with no skills → required/preferred full credit, projects neutral. Skills that normalize to `None` are ignored. Duplicate projects by name count once. Unicode/full-width input is NFKC-normalized. `algorithm_version` is bumped on any rule change, and the Power's `scoring-rules.md` must be updated in the same commit.

## 6. Application tracker (R5, R2.10–2.11)

`application_status.py` (pure):

```python
class ApplicationStatus(StrEnum): SAVED="Saved"; INTERESTED="Interested"; APPLIED="Applied"; ASSESSMENT="Assessment"; INTERVIEW="Interview"; REJECTED="Rejected"; OFFER="Offer"; WITHDRAWN="Withdrawn"
ALLOWED_TRANSITIONS: Mapping[ApplicationStatus, frozenset[ApplicationStatus]]
SUBMITTED_STATUSES = {Applied, Assessment, Interview, Offer, Rejected}
def transition(current: ApplicationStatus, target: ApplicationStatus) -> ApplicationStatus  # raises InvalidStatusTransition
```

| From | Allowed targets |
|---|---|
| Saved | Interested, Applied, Withdrawn |
| Interested | Saved, Applied, Withdrawn |
| Applied | Assessment, Interview, Offer, Rejected, Withdrawn |
| Assessment | Interview, Offer, Rejected, Withdrawn |
| Interview | Assessment, Offer, Rejected, Withdrawn |
| Offer | Withdrawn |
| Rejected | Interested (reopen) |
| Withdrawn | Interested (reopen) |

`transition(x, x)` returns `x` (no-op, R5.4). Any status may be used on create (users log past applications). Side effect in `ApplicationService`: when the resulting status is in `SUBMITTED_STATUSES` and `applied_at` is null, set `applied_at = clock.today()` (R5.6). Each successful create/status change/update/delete writes an `activity_events` row in the same transaction (R5.12).

`ApplicationService` methods: `create(user, ApplicationCreate)`, `list(user, status: list|None)`, `update(user, id, ApplicationUpdate)` (partial; status handled via `transition`), `delete(user, id)`, `mark_applied(user, job_id)` (R2.10/2.11: create with `Applied`, or transition from Saved/Interested; already `Applied` → return as is; other → `InvalidStatusTransition`), `meta()` (statuses in canonical order + transition map).

## 7. Dashboard and recommendations (R6, R7)

`DashboardService.get(user)` uses `clock.today()`/`clock.now()`; all metrics are computed fresh per request (R6.3). Hidden = `user_job_states.is_hidden` for this user.

| Metric | Definition |
|---|---|
| `total_jobs_discovered` | count of all jobs |
| `matching_jobs` | non-hidden jobs with score ≥ 60 |
| `applications_submitted` | applications with status ∈ SUBMITTED, plus `Withdrawn` with `applied_at` not null |
| `interviews_scheduled` | applications with status `Interview`, or with `interview_date ≥ now` and status not in {Rejected, Withdrawn, Offer} (each application counted once) |
| `offers_received` | status `Offer` |
| `response_rate` | `responded / applications_submitted × 100`, half-up to 1 decimal; `0.0` if submitted = 0. `responded` = status ∈ {Assessment, Interview, Offer, Rejected} |
| `upcoming_deadlines` | window `[today, today+14]`. Applications with status ∈ {Saved, Interested, Applied, Assessment, Interview} using `application.deadline ?? job.deadline` (`kind="application"`), plus bookmarked non-hidden jobs without an application using `job.deadline` (`kind="bookmark"`). Sort by deadline, then job id; max 8. Item: `{job_id, application_id, title, company, deadline, days_left, kind}` |
| `recent_activity` | last 10 `activity_events` by `created_at` desc, id desc |
| `top_recommendations` | `RecommendationService.recommend(user, 5)` as `{job_id, title, company, location, score}` |
| `status_breakdown` | `[{status, count}]` for all 8 statuses in canonical order (R6.4) |
| `applications_over_time` | last 8 ISO weeks (Monday start, including current): `[{week_start, count}]` by `applied_at` |
| `score_distribution` | non-hidden jobs bucketed `0-19, 20-39, 40-59, 60-79, 80-100`: `[{bucket, count}]` |

Metric arithmetic lives in pure functions (`dashboard_service.compute_metrics(apps, scores, today, now)`) so it is unit-testable without a DB.

`RecommendationService.recommend(user, limit)`: candidates = non-hidden jobs with no application or an application in {Saved, Interested}; order by score desc, deadline asc (nulls last), id asc; return `[{job: JobSummary, match_explanation}]` (R7).

## 8. REST API (R12)

All paths under `/api`; JSON only; the current user comes from `get_current_user` (§13.2). Request bodies use Pydantic models with `model_config = ConfigDict(extra="forbid")` (R12.4).

| Method | Path | Request | Success | Errors |
|---|---|---|---|---|
| GET | `/health` | — | 200 `{status, database, version}` | 503 db unavailable |
| GET | `/profile` | — | 200 `Profile` | 401, 503 |
| PUT | `/profile` | `ProfileUpdate` (full replace) | 200 `Profile` | 422, 409 `EMAIL_TAKEN` |
| GET | `/jobs` | query `q, employment_type[], work_mode[], experience_level[], location, source, skills (comma list), min_score, bookmarked, include_hidden, sort, order, page, page_size` | 200 `Page[JobSummary]` | 422 |
| GET | `/jobs/{id}` | — | 200 `JobDetail` (job + `match_explanation` + `state` + `application`) | 404 |
| POST | `/jobs/{id}/match` | — | 200 `MatchExplanation` | 404 |
| PUT / DELETE | `/jobs/{id}/bookmark` | — | 200 `JobState` | 404 |
| PUT / DELETE | `/jobs/{id}/hide` | — | 200 `JobState` | 404 |
| POST | `/jobs/{id}/apply` | — | 201 `Application` (200 if already Applied) | 404, 409 |
| POST | `/jobs/ingest` | `IngestRequest` | 200 `IngestResult` | 422, 413, 502 |
| GET | `/recommendations` | `limit` 1–20 (default 5) | 200 `list[Recommendation]` | 422 |
| GET | `/applications` | `status[]` | 200 `list[Application]` (with `job` summary) | 422 |
| GET | `/applications/meta` | — | 200 `{statuses[], transitions{}}` | — |
| POST | `/applications` | `ApplicationCreate` | 201 `Application` | 404 job, 409 `DUPLICATE_APPLICATION`, 422 |
| PATCH | `/applications/{id}` | `ApplicationUpdate` | 200 `Application` | 404, 409 `INVALID_STATUS_TRANSITION`, 422 |
| DELETE | `/applications/{id}` | — | 204 | 404 |
| GET | `/dashboard` | — | 200 `Dashboard` | — |
| POST | `/resume/analyze` | `ResumeAnalyzeRequest` | 200 `ResumeAnalysis` | 404, 422 `RESUME_EMPTY` |
| GET | `/interview/{job_id}` | — | 200 `InterviewPrep` | 404 |

`JobSummary`: `id, title, company, location, employment_type, work_mode, experience_level, salary_min, salary_max, salary_currency, salary_period, deadline, source, discovered_at, required_skills[], preferred_skills[], match_score, is_bookmarked, is_hidden, application_status`. `JobDetail` adds `description, application_url, min_education_level, match_explanation, application`.

Sort semantics: `match_score` (default desc), `discovered_at` (default desc), `deadline` (default asc), `title`/`company` (default asc, casefold), `salary` (uses `salary_max ?? salary_min`, default desc); nulls last; tie-break id asc (R2.5).

### 8.1 Validation rules

| Input | Rule | On failure |
|---|---|---|
| `name` | required, 1–100 chars after trim | 422 |
| `email` | required, `EmailStr`, ≤ 254, lowercased | 422; 409 `EMAIL_TAKEN` if used by another user |
| `location` | optional, ≤ 120 | 422 |
| `target_roles`, `preferred_locations` | ≤ 10 items, each 1–80 chars, trimmed, case-insensitive de-dupe | 422 |
| `preferred_work_modes` | list of `WorkMode`, unique | 422 |
| `experience_level`, `education_level` | optional enum | 422 |
| `education` | ≤ 10 entries; `institution` 1–150, `degree` ≤ 100, `field` ≤ 100, years 1950–2100, `start_year ≤ end_year` | 422 |
| `technical_skills` | ≤ 100 items, each 1–50 chars; stored once per normalized name | 422 |
| `soft_skills` | ≤ 50 items, 1–50 chars | 422 |
| `projects` | ≤ 20; `name` 1–120, `description` ≤ 2,000, `technologies` ≤ 20 × 1–50 chars, `url` optional http(s) | 422 |
| `certifications` | ≤ 30; `name` 1–120, `issuer` ≤ 120, `year` 1950–2100 | 422 |
| `resume_text` | ≤ 50,000 chars | 422 |
| URLs | optional, `http`/`https`, ≤ 300; `github_url` host `github.com`/`www.github.com`; `linkedin_url` host `linkedin.com`/`www.linkedin.com` | 422 |
| `ApplicationCreate` | `job_id` int ≥ 1 required; `status` enum default Saved; `notes` ≤ 5,000; `recruiter_name` ≤ 120; `recruiter_email` optional `EmailStr`; `outcome` ≤ 500; `applied_at`, `deadline` dates; `interview_date` tz-aware datetime (naive → assumed UTC) | 422 |
| `ApplicationUpdate` | same fields, all optional; explicit `null` clears nullable fields | 422 |
| Job list query | see R2.13; `skills` ≤ 10 entries | 422 |
| `IngestRequest` | §11.1 | 422 / 413 |
| `ResumeAnalyzeRequest` | `job_id` int ≥ 1 required; `resume_text` optional ≤ 50,000 | 422 |
| Path ids | int ≥ 1 | 422 |
| Request body size | ≤ 5 MB (Content-Length and streamed byte count) via `BodySizeLimitMiddleware` | 413 `PAYLOAD_TOO_LARGE` |

### 8.2 Error envelope

```json
{"error": {"code": "INVALID_STATUS_TRANSITION", "message": "Cannot move from Offer to Applied", "details": {"from": "Offer", "to": "Applied", "allowed": ["Withdrawn"]}}}
```

Validation errors: `details` is a list of `{loc, msg, type}` (Pydantic's `input` and `ctx` are stripped so user input is never echoed back).

## 9. Resume analysis (R8)

`ResumeService.analyze(user, job_id, resume_text | None)`.

### 9.1 Skill extraction

Normalize the resume text (NFKC, casefold, whitespace collapse). For every catalog canonical name and every alias, search with the regex `(?<![a-z0-9+#.])` + `re.escape(term)` + `(?![a-z0-9+#])` (whole-word/phrase, so `java` does not match `javascript`, `c` patterns only for `c++`/`c#`). Matches map to canonical names. Catalog = `CATALOG` keys ∪ `skills.normalized_name` from the DB ∪ the job's skills, so job-specific skills are detectable.

### 9.2 Outputs

- `matching_skills`: `(R ∪ P) ∩ resume_skills`, each `{skill, is_required}`.
- `missing_skills`: `(R ∪ P) − resume_skills`, each `{skill, is_required, in_profile}` (`in_profile` = in normalized profile skills).
- `relevant_projects`: profile projects whose technologies ∩ `R ∪ P` ≠ ∅, each `{name, matched_skills[], mentioned_in_resume}` (name appears in resume text, case-insensitive).
- `missing_keywords`: tokens from the job description (casefold, `[a-z][a-z0-9+#.]{2,}`), excluding a fixed English stop-word list and tokens present in the resume; keep tokens with frequency ≥ 2 or that are catalog skills; sort by frequency desc then alphabetically; max 15.
- `compatibility_score` + `match_explanation`: `compute_match(profile with technical_skills = resume_skills, job)` (R8.4).
- `word_count`, `resume_source` (`request` | `profile`).

### 9.3 Suggestion rules (each emits `{rule, message, evidence}`)

| Rule | Trigger | Message |
|---|---|---|
| `ADD_PROFILE_SKILL` | missing required/preferred skill with `in_profile=true` | `Your profile lists {Skill}, which this role requires/prefers, but your resume does not mention it.` |
| `GAP_REQUIRED_SKILL` | missing required skill with `in_profile=false` | `{Skill} is required and not evidenced; consider a project or course that demonstrates it.` |
| `MENTION_PROJECT` | relevant project with `mentioned_in_resume=false` | `Mention your project "{name}"; it uses {skills}.` |
| `ADD_KEYWORDS` | ≥ 3 missing keywords | `Consider reflecting these job terms where truthful: {top 5}.` |
| `QUANTIFY` | resume has < 3 numeric tokens (digits or `%`) | `Add measurable outcomes (numbers, percentages); found {n}.` |
| `LENGTH_SHORT` / `LENGTH_LONG` | word count < 150 / > 1,200 | `Resume has {n} words; aim for 300–900 for early-career roles.` |
| `ADD_LINKS` | profile has GitHub/portfolio URL not present in resume | `Add your {GitHub/portfolio} link.` |

Order: rule order above, then evidence alphabetically. The stored resume is never modified and no rewritten text is returned (R8.6).

## 10. Interview prep (R9, R15)

```python
class InterviewQuestionProvider(Protocol):
    name: str
    def generate(self, ctx: InterviewContext) -> InterviewPrep: ...
```

`InterviewContext` = job (title, company, required/preferred skills, employment type, experience level) + profile (projects, normalized skills). `TemplateInterviewProvider` (default) fills templates from `templates.py`:

| Section | Source | Limit |
|---|---|---|
| `role` | 6 role templates using `{title}`, `{company}`, `{employment_type}` | 5 (first 5) |
| `technical` | per required skill (alphabetical), 2 templates each; then preferred | 10 |
| `skill` | one "describe a time you used {Skill}" per required ∪ preferred skill, alphabetical | 8 |
| `project` | per profile project sorted by casefolded name; template chosen by whether it uses job skills | 3 (fallback generic project question if no projects) |
| `hr` | fixed list | 5 |

Each question: `{id, category, text, skill?}` where `id = "{category}-{n}"`. `prep_topics`: missing required (`high`), matched required (`medium`), missing preferred (`low`), each `{topic, reason, priority}`, ordered by priority then name. Response: `{job_id, provider, sections[{category, title, questions[]}], prep_topics[]}`.

`InterviewService` picks the provider at startup: `LlmEnrichedInterviewProvider` only when `LLM_ENABLED=true` and `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` are set (R15.1); otherwise template. The LLM provider first builds the template result, then calls the OpenAI-compatible `POST {LLM_BASE_URL}/chat/completions` (httpx, 15 s timeout, `Authorization: Bearer`), asking for up to 5 extra technical questions as a JSON array of strings; valid strings (≤ 300 chars, max 5) are appended to `technical` and `provider="llm"`. Any exception, non-2xx, timeout or parse failure → return the template result with `provider="template"` and log WARNING `llm_fallback reason=<type>` (R9.5, R15.3). The LLM is never used for scores or metrics (R15.2). Tests use `httpx.MockTransport`.

## 11. Job ingestion (R10)

### 11.1 Request

`IngestRequest`: `source` ∈ `fixture | remotive | arbeitnow | payload` (required); `fallback` bool default true; `limit` int 1–500 default 100; `format` ∈ `remotive | arbeitnow | normalized` (required iff `source=payload`); `payload` (object or list, required iff `source=payload`; ≤ 500 items after unwrapping). Violations → 422.

### 11.2 Sources (`sources.py`)

```python
class JobSource(Protocol):
    name: str
    def fetch(self, limit: int) -> RawBatch   # RawBatch(format, items: list[dict])
```

- `RemotiveSource`: `GET https://remotive.com/api/remote-jobs?limit={limit}`; items at `jobs`.
- `ArbeitnowSource`: `GET https://www.arbeitnow.com/api/job-board-api`; items at `data`; truncated to `limit`.
- `PayloadSource`: wraps the request payload (unwraps `jobs`/`data` keys if an object).
- `FixtureSource`: reads `DATA_DIR/seed_jobs.json` and `DATA_DIR/ingest/*.json` (sorted filenames; files must be normalized format or carry a top-level `format`). No caller-supplied paths.

`HttpFetcher` (shared by public sources): rejects URLs whose scheme is not `https` or host not in `INGEST_ALLOWED_HOSTS` (exact match) before any request; `httpx.Client(timeout=INGEST_TIMEOUT_SECONDS, follow_redirects=False)`; streams the body and aborts above `INGEST_MAX_BYTES` (5,000,000); requires 2xx and a JSON body. Failures raise `SourceUnavailable(reason)` with reasons `disallowed_host | timeout | network_error | http_status_<code> | too_large | invalid_json | unexpected_shape`.

### 11.3 Normalization (`normalizers.py`)

Each format has a normalizer `raw dict → JobCreate | Rejection(index, reason)`:
- HTML stripped with `html.parser`-based text extraction, entities unescaped, whitespace collapsed, truncated to 20,000 chars.
- Remotive: `external_id=str(id)`, `company=company_name`, `location=candidate_required_location or "Remote"`, `work_mode=remote`, `employment_type` from `job_type` (`full_time, part_time, contract, internship`; `freelance → contract`; other → `full_time`), `application_url=url`, `required_skills = tags` (normalized, max 15), `preferred_skills` = catalog skills found in the description not in required (max 10).
- Arbeitnow: `external_id=slug`, `work_mode = remote if remote else onsite`, `employment_type` from `job_types` (contains `intern`/`praktikum` → internship, `part` → part_time, `contract`/`freelance` → contract, else full_time), tags → required, description skills → preferred.
- Normalized: the seed format (§12), fields as in the jobs table; `deadline` (date) or `deadline_in_days` (int, resolved against `clock.today()`).
- All formats: if the title contains `intern`/`internship`/`trainee`, employment type becomes `internship`; `experience_level` inferred from title tokens when absent (`intern|internship|trainee → internship`, `graduate|entry|new grad → entry`, `junior|jr → junior`, `mid|intermediate → mid`, `senior|sr|lead|principal|staff → senior`, else null).
- `JobCreate` validation: title/company/location 1–200, `application_url` http(s) ≤ 500, ≤ 30 required and ≤ 30 preferred skills, salaries ≥ 0 and min ≤ max, currency `^[A-Z]{3}$`.

### 11.4 Dedupe and persistence (`service.py`)

`fingerprint = sha256(f"{n(title)}|{n(company)}|{n(location)}")` where `n` = casefold, non-alphanumerics → space, collapse, strip. For each valid item, in input order, within one transaction:
1. Existing job with same (source, external_id) → update mutable fields and skills; if the new fingerprint collides with a *different* job, skip the update and count `duplicates`. Else count `updated`.
2. Else existing job with the same fingerprint → count `duplicates` (skip).
3. Else insert → `created`. In-batch duplicates are caught by the same checks (fingerprints of earlier inserts are tracked in a set).
One `jobs_ingested` activity event is written per run. All fetching and validation happen before the first write, so a source failure never causes partial writes (R10.7).

### 11.5 Fallback

`IngestionService.ingest(req)`: try the requested source; on `SourceUnavailable` with `fallback=true`, run `FixtureSource`, set `fallback_used=true`, `source="fixture"`, add `{index: null, reason: "<source>: <reason>"}` to `errors`, log WARNING. With `fallback=false`, raise `UpstreamUnavailableError` → 502. `IngestResult`: `{requested_source, source, fallback_used, fetched, created, updated, duplicates, rejected, errors[≤50]}`. The MCP workflow (Kiro agent fetches with `mcp-server-fetch`, saves to `data/ingest/*.json` or posts `source=payload`) feeds the same pipeline; the app never depends on MCP (R10.9).

## 12. Seed data (R11)

Files: `data/seed_profile.json` (one user + skills), `data/seed_jobs.json` (≥ 30 jobs, normalized format, `source` forced to `seed`, `external_id` like `seed-001`, `deadline_in_days` relative), `data/seed_applications.json` (≥ 10, keyed by `job_external_id`, with `status`, `applied_days_ago`, `deadline_in_days`, `interview_in_days`, recruiter placeholders such as `recruiter@example.com`, notes, outcome; ≥ 6 distinct statuses). `SeedService.run()`:
1. Upsert catalog skills (`CATALOG` + all seed skills) by `normalized_name`.
2. Create the demo user (`DEMO_USER_EMAIL`, `DEMO_USER_NAME`, profile from file) only if absent; never overwrite an existing user (R11.2).
3. Ingest jobs through `IngestionService` with the normalized format (upsert by `seed`/`external_id`).
4. Insert each seed application only if no application exists for (user, job); write `application_created` events.
Exposed as `python -m app.cli seed` (exit 0 on success, 1 with a logged error on failure). Docker runs it after `alembic upgrade head` (R11.4).

## 13. Configuration and identity (R13)

### 13.1 Settings (`app/core/config.py`, pydantic-settings, `.env` supported)

| Variable | Type / default | Notes |
|---|---|---|
| `APP_ENV` | `development` | `development | test | production` |
| `DATABASE_URL` | **required** | startup fails fast with a clear message if missing |
| `TEST_DATABASE_URL` | optional | tests use it if set, else in-memory SQLite |
| `CORS_ORIGINS` | `http://localhost:5173` | comma list |
| `DEMO_USER_EMAIL` / `DEMO_USER_NAME` | `demo@internpilot.dev` / `Demo Student` | |
| `DATA_DIR` | `<repo>/data` | `/data` in Docker |
| `INGEST_ALLOWED_HOSTS` | `remotive.com,www.arbeitnow.com` | |
| `INGEST_TIMEOUT_SECONDS` | `10` (1–60) | |
| `INGEST_MAX_BYTES` | `5000000` | |
| `LLM_ENABLED` | `false` | |
| `LLM_PROVIDER` | `openai_compatible` | only supported value |
| `LLM_BASE_URL`, `LLM_MODEL` | empty | |
| `LLM_API_KEY` | empty, `SecretStr` | never logged |
| `LOG_LEVEL` | `INFO` | |

`.env.example` lists all of them with placeholder values only.

### 13.2 Current user

`get_current_user(request, session)`: header `X-Demo-User` (email, ≤ 254) → that user or 401 `UNKNOWN_DEMO_USER`; no header → user with `DEMO_USER_EMAIL` or 503 `DEMO_USER_NOT_SEEDED`. The frontend sends no header by default. Documented as demo-only in README and `docs/api.md` (R13.5).

## 14. Error handling and logging

`app/core/errors.py`: `AppError(code, message, status_code, details)` with subclasses `NotFoundError(404)`, `ConflictError(409)` → `DuplicateApplicationError`, `InvalidStatusTransitionError`, `EmailTakenError`; `RequestValidationAppError(422)` → `ResumeEmptyError`; `PayloadTooLargeError(413)`; `UpstreamUnavailableError(502)`; `UnknownDemoUserError(401)`; `NotReadyError(503)`. Handlers registered in `create_app` map: `AppError` → its envelope; `RequestValidationError` → 422 `VALIDATION_ERROR`; `sqlalchemy.exc.IntegrityError` → 409 `CONFLICT` (WARNING); `sqlalchemy.exc.OperationalError` → 503 `DATABASE_UNAVAILABLE` (ERROR); any other `Exception` → 500 `INTERNAL_ERROR`, "An unexpected error occurred." (ERROR with traceback and request id, never in the response).

| Operation | Failure | Recoverable? | Caller receives | Log |
|---|---|---|---|---|
| Any request | invalid input | yes | 422 `VALIDATION_ERROR` | none (DEBUG) |
| Any request | DB unreachable | yes (retry) | 503 `DATABASE_UNAVAILABLE` | ERROR |
| Resolve user | unknown header / unseeded | yes | 401 / 503 | WARNING |
| Profile PUT | email taken | yes | 409 `EMAIL_TAKEN` | INFO |
| Job-scoped calls | job missing | yes | 404 `NOT_FOUND` | none |
| Create application | exists (pre-check or IntegrityError race) | yes | 409 `DUPLICATE_APPLICATION` | INFO |
| Update/mark applied | disallowed transition | yes | 409 `INVALID_STATUS_TRANSITION` with `allowed` | INFO |
| Resume analyze | both texts empty | yes | 422 `RESUME_EMPTY` | none |
| Ingest public source | network/timeout/status/size/JSON/host | yes | 200 with `fallback_used` (fallback) or 502 | WARNING |
| Ingest item | invalid item | yes | counted in `rejected` + `errors` | DEBUG per item, INFO summary |
| Ingest write | DB error | fatal for the run | rollback, 500/503 | ERROR |
| LLM enrichment | any failure | yes | template result | WARNING |
| Seed CLI | file missing/invalid | fatal | exit 1 | ERROR |
| Startup | `DATABASE_URL` missing | fatal | process exits | CRITICAL |
| Health | DB check fails | yes | 503 `{status:"degraded", database:"unavailable"}` | WARNING |

Logging: stdlib `logging`, format `%(asctime)s %(levelname)s %(name)s [%(request_id)s] %(message)s`; `RequestIdMiddleware` accepts a safe incoming `X-Request-ID` (`^[A-Za-z0-9-]{1,64}$`) or generates a UUID4, stores it in a context var and returns it (R12.5); one INFO access line per request (method, path, status, duration ms). Never log request bodies, resume text, emails of recruiters, or `LLM_API_KEY`.

## 15. Frontend design

### 15.1 Structure

```
frontend/
  index.html, vite.config.ts, tailwind.config.ts, postcss.config.js, tsconfig*.json, eslint.config.js, .prettierrc
  Dockerfile, nginx.conf
  src/main.tsx, src/App.tsx (QueryClientProvider, ToastProvider, BrowserRouter, routes)
  src/api/client.ts            fetch wrapper: base URL from VITE_API_BASE_URL, JSON, ApiError(code, message, status, details)
  src/api/{profile,jobs,applications,dashboard,recommendations,resume,interview,ingest}.ts
  src/types/api.ts             TS mirrors of backend schemas
  src/hooks/{useProfile,useJobs,useJob,useApplications,useDashboard,useRecommendations,useResumeAnalysis,useInterviewPrep}.ts
  src/lib/{queryKeys.ts,format.ts,scoreBand.ts}
  src/components/layout/{AppShell,Sidebar,TopBar}.tsx
  src/components/ui/{Button,Card,Badge,Input,Select,Textarea,Dialog,Toast,Skeleton,EmptyState,ErrorState,Tabs}.tsx
  src/components/match/{MatchScoreRing,MatchExplanationPanel,FactorBreakdown}.tsx
  src/components/jobs/{JobCard,JobFilters,JobList,Pagination,JobActions}.tsx
  src/components/applications/{ApplicationTable,KanbanBoard,KanbanColumn,ApplicationCard,ApplicationForm,MoveToMenu}.tsx
  src/components/dashboard/{StatCard,StatusBreakdownChart,ApplicationsOverTimeChart,ScoreDistributionChart,UpcomingDeadlines,RecentActivity,TopRecommendations}.tsx
  src/pages/{DashboardPage,JobsPage,JobDetailPage,ApplicationsPage,ResumePage,InterviewPage,ProfilePage,NotFoundPage}.tsx
  tests/**/*.test.tsx, tests/setup.ts
```

Routes: `/` → redirect `/dashboard`; `/jobs`; `/jobs/:jobId`; `/applications?view=table|board`; `/resume?jobId=`; `/interview/:jobId` (and `/interview` with a job picker); `/profile`; `*` → NotFound.

### 15.2 Behavior

- Job list filters/sort/page live in the URL (`useSearchParams`); search input debounced 300 ms.
- Mutations invalidate: application changes → `applications`, `dashboard`, `jobs`, `recommendations`, `job`; profile save → everything match-dependent; bookmark/hide → `jobs`, `job`, `dashboard`, `recommendations`. No optimistic updates for status moves (server is the source of truth for transitions); the card shows a pending state.
- Kanban: 8 columns from `/applications/meta`; cards are `draggable`; drop targets not in `transitions[current]` show a not-allowed style and are ignored with an info toast; each card has a "Move to…" menu button (keyboard operable, lists only allowed targets).
- `ApiError` messages surface in toasts; 409 transition errors show the allowed targets.
- Design tokens (Tailwind `theme.extend`): `ink` neutrals (slate), `pilot` primary (teal `#0F766E` family), `signal` accent (amber `#B45309`), semantic `success/warning/danger`; font Inter with system fallback; radius `lg`; score bands ≥ 80 `success`, 60–79 `pilot`, 40–59 `warning`, < 40 `danger`, always alongside the number (R14.5). Text tokens meet 4.5:1 on their backgrounds.
- `MatchScoreRing`: SVG circle with `role="img"` and `aria-label="Match score 87 out of 100"`, visible `87/100`; panel title reads `MATCH SCORE: 87/100`.

## 16. Testing strategy

| Level | Location | What |
|---|---|---|
| Unit | `backend/tests/unit/` | normalization, each factor rule and reason template, rounding, state machine, dashboard `compute_metrics`, resume extraction/suggestions, interview templates, normalizers, fingerprint, HttpFetcher guards (MockTransport) |
| Integration | `backend/tests/integration/` | repositories + services on a real session (SQLite default, Postgres via `TEST_DATABASE_URL`): ingestion dedupe/update/fallback, seed idempotency, application uniqueness and check constraint, cascade |
| API | `backend/tests/api/` | `TestClient` for every endpoint: success shapes, error envelope, 404/409/422/413, request id header |
| Property | `backend/tests/property/test_matching_properties.py`, `test_application_status_properties.py` | P1–P6 (§17) with a registered Hypothesis profile (`max_examples=200`, `derandomize=True`, `deadline=None`) |
| Frontend | `frontend/tests/` | `MatchScoreRing`, `MatchExplanationPanel` (+/- prefixes), `KanbanBoard` (allowed moves only, Move-to menu by keyboard), `JobFilters` URL sync, `api/client` error parsing, Dashboard empty state |

Dates are controlled with `FixedClock` injected via `get_clock` override. No test touches the network. Coverage gates: backend ≥ 80% lines, `app/services/matching` ≥ 95% (`pytest --cov`); frontend ≥ 60% lines for `src/components` and `src/lib`.

## 17. Correctness properties ↔ requirements

| Property | Statement (Hypothesis strategy) | Requirements | Test |
|---|---|---|---|
| P1 Score bounds | For arbitrary `MatchProfile`/`MatchJob` (random skill strings incl. catalog skills, aliases, unicode; random enums incl. None; 0–20 projects): `0 ≤ score ≤ 100`, `isinstance(score, int)`, each factor `0 ≤ points ≤ weight`, `score == floor(Σ points + 1/2)`, exactly 8 factors. | R3.1, R3.3, R3.4, R4.1, R4.2 | `test_p1_score_is_bounded` |
| P2 Monotonicity | For any p, j and any `s ∈ j.required ∪ j.preferred`: `score(p + s) ≥ score(p)`. For any `s` with `normalize_skill(s) ∉ R ∪ P`: result unchanged. | R3.5, R3.6 | `test_p2_adding_matching_skill_never_lowers_score`, `test_p2_adding_unrelated_skill_changes_nothing` |
| P3 Duplicates | For p and a variant whose skills are p's skills plus duplicates, case/whitespace variants and aliases: identical `MatchResult`. | R3.2, R3.7 | `test_p3_duplicate_skills_have_no_impact` |
| P4 Missing skills | For any p, j: every `r ∈ R − S` is in `missing_required_skills` and not in `matched_required_skills`; required points `= 35·|R∩S|/|R|`; if `S ∩ R = ∅ ≠ R` then required points = 0 (same for preferred). | R3.8, R3.9, R4.3 | `test_p4_missing_required_skills_get_no_credit` |
| P5 Determinism | `compute_match(p, j) == compute_match(p, j)` and equals the result for p, j with all tuples permuted. | R3.10, R3.11, R4.6 | `test_p5_match_is_deterministic_and_order_independent` |
| P6 Status validity | For any start status and any sequence of target strings (valid statuses and arbitrary text): after each step the status is exactly one member of `ApplicationStatus`; invalid targets raise and leave it unchanged; the Pydantic schema rejects non-members; a service-level stateful test (Hypothesis `RuleBasedStateMachine` over `ApplicationService` on SQLite) checks the stored row too. | R5.2, R5.4, R5.5 | `test_p6_application_always_has_one_valid_status` |

Each test docstring cites its property and requirement IDs. `pytest backend/tests/property -v` runs them all.

## 18. Docker and local run

`docker-compose.yml`:
- `db`: `postgres:16-alpine`, env from `POSTGRES_*`, named volume `pgdata`, healthcheck `pg_isready`.
- `backend`: build `./backend` (`python:3.12-slim`, non-root user), `DATA_DIR=/data`, `./data:/data:ro`, `depends_on: db (service_healthy)`, entrypoint `docker-entrypoint.sh` → `alembic upgrade head`, `python -m app.cli seed`, `uvicorn app.main:app --host 0.0.0.0 --port 8000`; port 8000.
- `frontend`: multi-stage (`node:22-alpine` build with `VITE_API_BASE_URL` build arg → `nginx:1.27-alpine`, SPA fallback in `nginx.conf`); port `5173:80`.
Secrets come from `.env` (gitignored); compose uses `${VAR:-default}` placeholders that match `.env.example`.

Local dev: `python -m venv .venv`, `pip install -r requirements-dev.txt`, `alembic upgrade head`, `python -m app.cli seed`, `uvicorn app.main:app --reload`; `npm ci`, `npm run dev`. Exact commands live in README.
