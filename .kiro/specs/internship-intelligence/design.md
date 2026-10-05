# Design: Internship Intelligence (InternPilot AI)

## 1. Overview

InternPilot AI is a three-tier web application: a React + TypeScript single-page app talks REST/JSON to a FastAPI backend, which persists to PostgreSQL through SQLAlchemy 2 repositories. The heart of the system is a pure, deterministic matching engine (`app/services/matching/`) that turns a (profile, job) pair into a 0–100 score and a `match_explanation`. Everything else — job lists, recommendations, dashboard, resume analysis — calls that one engine, so a pair never shows two scores (R3.12). Job ingestion pulls from allow-listed public APIs, captured MCP payloads or local fixtures, normalizes and dedupes, and always has an offline fallback (R10). Interview prep is template-driven behind a provider interface, with an optional OpenAI-compatible LLM enrichment that is off by default (R9, R15). A single seeded demo user is resolved by a request dependency; this is explicitly not production auth (R13).

Every section below names the requirement IDs it satisfies. Where alternatives existed, the chosen option is stated with its reason; the implementer should not re-open these decisions.

## 2. Technology stack (locked)

| Layer | Choice | Version line (pin exact patch at install) |
|---|---|---|
| Frontend runtime | Node 22, Vite 5, React 18, TypeScript 5 (`strict`) | vite 5.4.x, react 18.3.x, typescript 5.6.x |
| Styling | Tailwind CSS 3 with design tokens in `tailwind.config.ts` | tailwindcss 3.4.x, postcss 8, autoprefixer 10 |
| Routing | React Router 6 (data-less `BrowserRouter` + `Routes`) | react-router-dom 6.30.x (bumped from 6.28.x to fix a high-severity advisory) |
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

The profile → `MatchProfile` and job → `MatchJob` mapping lives in `app/services/matching_inputs.py`; list, detail and `POST /api/jobs/{id}/match` all use it (R3.12). `min_score` is applied to the scored candidates before sorting and pagination, so `total` counts only qualifying jobs; `match_score` sorts via `sort_jobs` like the other keys (desc by default, id asc tie-break).

### 3.4 Frontend layers

`pages/*` compose `components/*` and call hooks from `hooks/*`; hooks wrap TanStack Query around typed functions in `api/*`; `api/client.ts` is the only place that calls `fetch`. Components receive data and callbacks via props and contain no scoring, transition or metric logic (R14.6). Allowed status moves come from `GET /api/applications/meta`.

## 4. Data model

All tables use integer surrogate PKs, `created_at`/`updated_at` in UTC (server default `now()`, `onupdate`). Every timestamp column (`created_at`, `updated_at`, `discovered_at`, `interview_date`) uses the `UTCDateTime` `TypeDecorator` from `app/models/base.py` (impl `DateTime(timezone=True)`, `cache_ok=True`): on bind it raises `ValueError` for naive datetimes and converts aware values to UTC; on load it attaches `timezone.utc` when the driver returns a naive value (SQLite does not persist offsets). This keeps comparisons with the aware `clock.now()` valid on both databases (NFR2). Pure `date` columns use plain `Date`. JSON columns use `sa.JSON().with_variant(JSONB, "postgresql")` so SQLite tests run unchanged (NFR2). Enum-like columns are `String` + `CheckConstraint` (portable, migration-friendly) rather than native PG enums.

### 4.1 Tables

**users**
| Column | Type | Notes |
|---|---|---|
| id | int PK | |
| name | varchar(100) not null | |
| email | varchar(254) not null **unique** | stored lowercase; editable by the user |
| seed_key | varchar(32) null **unique** (`uq_users_seed_key`) | `'demo'` for the seeded demo user, null otherwise; stable identity for default-user resolution and seed idempotency (§12, §13.2) |
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
| Exactly one demo user | `uq_users_seed_key`; `SeedService` and `get_current_user` look up `seed_key='demo'` | Email is user-editable, so it cannot be the identity (R11.2, R13.2a). |
| Timestamps are aware UTC | `UTCDateTime` type decorator (models) | One place covers every column on both databases (NFR2). |

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
2. Replace any whitespace run with a single space.
3. Repeat until the string no longer changes: strip whitespace; strip leading/trailing characters in `EDGE_PUNCTUATION = ` `` ,;:|/\()[]{}"'` ``; strip one trailing `.`. (Internal `.`, `+`, `#` are preserved: `node.js`, `c++`, `c#`; a leading `.` is preserved: `.net`.) So `" React ,"`, `"( React )"` and `"React."` all become `react`.
4. Look up `ALIASES` (in `skill_catalog.py`); if present, replace with the canonical name. Every alias value is itself a canonical name that is a fixed point of steps 1–3 and not an alias key, so the function is idempotent: `normalize_skill(normalize_skill(x)) == normalize_skill(x)` whenever the inner result is not `None`.
5. Return `None` if empty or longer than 50 characters. The engine and ingestion ignore `None` results; profile input rejects them with 422 (§8.1, R1.3).

Tests: `test_normalize_skill_is_idempotent` (examples) plus a Hypothesis check in `tests/property/test_normalization_properties.py` that `normalize_skill(normalize_skill(x) or "") == normalize_skill(x)` for arbitrary text and for catalog/alias names wrapped in random edge punctuation and whitespace; a unit test asserts every `ALIASES` value is a fixed point.

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

`factors` always has all eight entries in §5.3 order. `detail` templates: skills `"{m} of {n} required|preferred skills matched"` (or `"none listed"`), role `"best match: {role}"`/`"no target roles"`/`"no comparable title terms"`; experience `"{user} profile, {job} role"`/`"level not specified"`; location `"remote role"`/`"city or region matches"`/`"country matches"`/`"outside preferred locations"`/`"no locations in profile"`; work mode `"{Mode} is preferred"`/`"Hybrid is a partial match"`/`"{Mode} is not preferred"`/`"no preferred work modes"`; education `"no minimum requirement"`/`"meets {job}"`/`"one level below {job}"`/`"below {job}"`/`"education not specified"`; projects `"{k} of {groups} projects use the role's skills"`/`"no job skills to compare"`. Skill lists hold display names sorted by normalized name.

### 5.6 Edge cases

Empty profile → all neutral/zero factors; score is still in range. Job with no skills → required/preferred full credit, projects neutral. Skills that normalize to `None` are ignored by the engine. Projects whose names collide after casefold form one group (§5.3), so they count once and the reason text does not depend on their order. Target roles made only of stop tokens (`"Intern"`, `"Senior"`) are not usable and never cause a division by zero. Unicode/full-width input is NFKC-normalized. `algorithm_version` is bumped on any rule change, and the Power's `scoring-rules.md` must be updated in the same commit.

## 6. Application tracker (R5, R2.10–2.11)

`application_status.py` (pure):

```python
class ApplicationStatus(StrEnum): SAVED="Saved"; INTERESTED="Interested"; APPLIED="Applied"; ASSESSMENT="Assessment"; INTERVIEW="Interview"; REJECTED="Rejected"; OFFER="Offer"; WITHDRAWN="Withdrawn"
ALLOWED_TRANSITIONS: Mapping[ApplicationStatus, frozenset[ApplicationStatus]]
SUBMITTED_STATUSES = {Applied, Assessment, Interview, Offer, Rejected}
def transition(current: ApplicationStatus, target: ApplicationStatus) -> ApplicationStatus  # raises InvalidStatusTransitionError
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

Update rules (settled in 2.12): a PATCH applies only fields present in the body (`model_fields_set`); explicit `null` clears nullable fields, while `null` for `status` or `notes` is 422. The `applied_at` side effect fires only on create or an actual status move, so clearing `applied_at` on an application already in a submitted status is allowed. A PATCH that changes nothing (including a same-status move) is a no-op success: no write, no event, `updated_at` unchanged. A PATCH that changes the status writes one `status_changed` event (even if other fields also changed); otherwise a field change writes one `application_updated` event. Event messages are capped at 300 characters. `GET /applications/meta` does not resolve the current user (it is user-independent).

`ApplicationService` methods: `create(user, ApplicationCreate)`, `list_applications(user, statuses: list|None)` (not `list`, which would shadow the builtin in annotations inside the class body), `update(user, id, ApplicationUpdate)` (partial; status handled via `transition`), `delete(user, id)`, `mark_applied(user, job_id) -> MarkAppliedResult(application, created: bool)` (R2.10/2.11: no application → create with `Applied`, `created=True` → route returns 201; Saved/Interested → transition to `Applied`, `created=False` → 200; already `Applied` → returned unchanged, `created=False` → 200, no activity event; any other status → `InvalidStatusTransitionError` → 409). The route picks the status code from `created` only; it does not branch on domain state., `meta()` (statuses in canonical order + transition map).

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
| GET | `/health` | — | 200 `{"status":"ok","database":"ok","version":"<app version>"}` | 503 `{"status":"degraded","database":"unavailable","version":"<app version>"}` (health body, not the error envelope; R12.2, R12.6) |
| GET | `/profile` | — | 200 `Profile` | 401, 503 |
| PUT | `/profile` | `ProfileUpdate` (full replace) | 200 `Profile` | 422, 409 `EMAIL_TAKEN` |
| GET | `/jobs` | query `q, employment_type[], work_mode[], experience_level[], location, source, skills (comma list), min_score, bookmarked, include_hidden, sort, order, page, page_size` | 200 `Page[JobSummary]` | 422 |
| GET | `/jobs/{id}` | — | 200 `JobDetail` (§8.3: summary fields incl. flags + `match_explanation` + `application`) | 404 |
| POST | `/jobs/{id}/match` | — | 200 `MatchExplanation` | 404 |
| PUT / DELETE | `/jobs/{id}/bookmark` | — | 200 `JobState` | 404 |
| PUT / DELETE | `/jobs/{id}/hide` | — | 200 `JobState` | 404 |
| POST | `/jobs/{id}/apply` | — | 201 `Application` when created; 200 `Application` when an existing Saved/Interested application moves to Applied or it is already Applied | 404, 409 `INVALID_STATUS_TRANSITION` |
| POST | `/jobs/ingest` | `IngestRequest` | 200 `IngestResult` | 422, 413, 502 |
| GET | `/recommendations` | `limit` 1–20 (default 5) | 200 `list[Recommendation]` | 422 |
| GET | `/applications` | `status[]` | 200 `list[Application]` (with `job` summary; unpaginated by design, max 500 — see below) | 422 |
| GET | `/applications/meta` | — | 200 `{statuses[], transitions{}}` | — |
| POST | `/applications` | `ApplicationCreate` | 201 `Application` | 404 job, 409 `DUPLICATE_APPLICATION`, 422 |
| PATCH | `/applications/{id}` | `ApplicationUpdate` | 200 `Application` | 404, 409 `INVALID_STATUS_TRANSITION`, 422 |
| DELETE | `/applications/{id}` | — | 204 | 404 |
| GET | `/dashboard` | — | 200 `Dashboard` | — |
| POST | `/resume/analyze` | `ResumeAnalyzeRequest` | 200 `ResumeAnalysis` | 404, 422 `RESUME_EMPTY` |
| GET | `/interview/{job_id}` | — | 200 `InterviewPrep` | 404 |

`JobSummary`: `id, title, company, location, employment_type, work_mode, experience_level, salary_min, salary_max, salary_currency, salary_period, deadline, source, discovered_at, required_skills[], preferred_skills[], match_score, is_bookmarked, is_hidden, application_status`. `JobDetail` adds `description, application_url, min_education_level, match_explanation, application`.

Pagination exception: `GET /applications` returns a plain list because the Kanban board needs the user's full set in one response to place cards in columns. The set is per user and bounded: `ApplicationRepository.list_for_user` applies `LIMIT 500` ordered by `updated_at` desc, id desc, and the service logs WARNING when the cap is reached. This is the only unpaginated growing list; `coding-standards.md` records the exception.

Sort semantics: `match_score` (default desc), `discovered_at` (default desc), `deadline` (default asc), `title`/`company` (default asc, casefold), `salary` (uses `salary_max ?? salary_min`, default desc); nulls last; tie-break id asc (R2.5). `order` is optional; when omitted the key's default applies.

Job list and flag rules (settled in 2.13): `page` defaults to 1 and `page_size` to 20; `total_pages = ceil(total / page_size)`, so it is 0 when `total` is 0. The query string is validated as one `JobListParams` model (FastAPI query-parameter model), so unknown query parameters are 422 like unknown body fields. Multi-valued filters are repeated parameters (`work_mode=remote&work_mode=onsite`). `skills` is comma-separated: blank entries are ignored, every other entry must normalize (§5.1) or the request is 422, at most 10 distinct normalized skills; a job matches when any of its required or preferred skills is in the set. `q` and `location` are trimmed; blank means "no filter". Bookmark/hide state rows are created only when a flag is first set; clearing a flag on a job without a row returns `{false, false}` and writes nothing. A `job_bookmarked` / `job_hidden` activity event is written only when the flag turns on; clearing a flag and repeating a request write no event.

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
| `technical_skills` | ≤ 100 items, each 1–50 chars; each must satisfy `normalize_skill(item) is not None` (a field validator; e.g. `"(,)"` fails); stored once per normalized name | 422 (`loc` points at the offending index) |
| `soft_skills` | ≤ 50 items, 1–50 chars | 422 |
| `projects` | ≤ 20; `name` 1–120, `description` ≤ 2,000, `technologies` ≤ 20 × 1–50 chars, `url` optional http(s) | 422 |
| `certifications` | ≤ 30; `name` 1–120, `issuer` ≤ 120, `year` 1950–2100 | 422 |
| `resume_text` | ≤ 50,000 chars | 422 |
| URLs | optional, `http`/`https`, ≤ 300; `github_url` host `github.com`/`www.github.com`; `linkedin_url` host `linkedin.com`/`www.linkedin.com` | 422 |
| `ApplicationCreate` | `job_id` int ≥ 1 required; `status` enum default Saved; `notes` ≤ 5,000; `recruiter_name` ≤ 120; `recruiter_email` optional `EmailStr`; `outcome` ≤ 500; `applied_at`, `deadline` dates; `interview_date` tz-aware datetime (naive → assumed UTC) | 422 |
| `ApplicationUpdate` | same fields, all optional; explicit `null` clears nullable fields | 422 |
| Job list query | see R2.13; `skills` ≤ 10 entries | 422 |
| `IngestRequest` | §11.1 | 422 / 413 |
| `ResumeAnalyzeRequest` | `job_id` int ≥ 1 required; `resume_text` optional ≤ 50,000. The service treats `None`, empty and whitespace-only text the same: fall back to the profile text; if that is also empty/whitespace-only → `ResumeEmptyError` | 422 / 422 `RESUME_EMPTY` |
| Profile optional text/URLs | `location`, `degree`, `field`, `issuer` and every URL field: an empty or whitespace-only string is treated as `null`. URLs must be absolute with a host, contain no whitespace and no `user:pass@` credentials; they are stored as submitted (trimmed). New catalog skills created from a profile take `display_skill(normalized)` as their display name (§5.1), so the name never depends on the submitted spelling or order | 422 |
| Path ids | int ≥ 1 | 422 |
| Request body size | ≤ 5 MB (Content-Length and streamed byte count) via `BodySizeLimitMiddleware` | 413 `PAYLOAD_TOO_LARGE` |

### 8.2 Error envelope

```json
{"error": {"code": "INVALID_STATUS_TRANSITION", "message": "Cannot move from Offer to Applied", "details": {"from": "Offer", "to": "Applied", "allowed": ["Withdrawn"]}}}
```

Validation errors: `details` is a list of `{loc, msg, type}` (Pydantic's `input` and `ctx` are stripped so user input is never echoed back).

### 8.3 Response schemas

Exact field lists; `frontend/src/types/api.ts` mirrors these names and types 1:1. Dates are `YYYY-MM-DD` strings, timestamps ISO-8601 UTC with `Z`. `?` marks nullable fields (always present, value may be `null`). Enums serialize as their string values.

| Schema | Fields |
|---|---|
| `Page[T]` | `items: T[]`, `total: int`, `page: int`, `page_size: int`, `total_pages: int` |
| `EducationEntry` | `institution: str`, `degree: str?`, `field: str?`, `start_year: int?`, `end_year: int?` |
| `Project` | `name: str`, `description: str` (default `""`), `technologies: str[]`, `url: str?` |
| `Certification` | `name: str`, `issuer: str?`, `year: int?` |
| `Profile` | `id`, `name`, `email`, `location?`, `target_roles: str[]`, `preferred_locations: str[]`, `preferred_work_modes: WorkMode[]`, `experience_level: ExperienceLevel?`, `education_level: EducationLevel?`, `education: EducationEntry[]`, `technical_skills: str[]` (display names, sorted by normalized name), `soft_skills: str[]`, `projects: Project[]`, `certifications: Certification[]`, `resume_text: str`, `github_url?`, `portfolio_url?`, `linkedin_url?`, `created_at`, `updated_at`. `seed_key` is internal and never returned. |
| `ProfileUpdate` (request) | every `Profile` field except `id`, `created_at`, `updated_at`; full replace |
| `JobState` | `job_id: int`, `is_bookmarked: bool`, `is_hidden: bool` |
| `JobSummary` | as listed under §8 above (`required_skills`/`preferred_skills` are display names sorted by normalized name; `match_score: int`; `application_status: ApplicationStatus?`) |
| `JobDetail` | all `JobSummary` fields + `description: str`, `application_url: str`, `min_education_level: EducationLevel?`, `match_explanation: MatchExplanation`, `application: Application?` |
| `MatchExplanation` | §5.5: `job_id`, `score`, `algorithm_version`, `factors: Factor[]` (`key`, `label`, `weight: int`, `points: float`, `ratio: float`, `detail: str`), `matched_required_skills`, `missing_required_skills`, `matched_preferred_skills`, `missing_preferred_skills`, `positive_reasons`, `negative_reasons` (all `str[]`) |
| `ApplicationJob` | `id`, `title`, `company`, `location`, `deadline?` |
| `Application` | `id`, `job_id`, `status: ApplicationStatus`, `applied_at?` (date), `deadline?` (date), `interview_date?` (timestamp), `recruiter_name?`, `recruiter_email?`, `notes: str`, `outcome?`, `created_at`, `updated_at`, `job: ApplicationJob` |
| `ApplicationsMeta` | `statuses: ApplicationStatus[]` (canonical order), `transitions: {[status]: ApplicationStatus[]}` (targets in canonical order) |
| `Recommendation` | `job: JobSummary`, `match_explanation: MatchExplanation` |
| `Dashboard` | `total_jobs_discovered: int`, `matching_jobs: int`, `applications_submitted: int`, `interviews_scheduled: int`, `offers_received: int`, `response_rate: float`, `upcoming_deadlines: {job_id, application_id?, title, company, deadline, days_left: int, kind: "application"\|"bookmark"}[]`, `recent_activity: {id, type, message, job_id?, application_id?, created_at}[]`, `top_recommendations: {job_id, title, company, location, score: int}[]`, `status_breakdown: {status, count}[]`, `applications_over_time: {week_start: date, count}[]`, `score_distribution: {bucket: "0-19"\|"20-39"\|"40-59"\|"60-79"\|"80-100", count}[]` |
| `ResumeAnalysis` | `job_id`, `resume_source: "request"\|"profile"`, `word_count: int`, `compatibility_score: int`, `matching_skills: {skill, is_required}[]`, `missing_skills: {skill, is_required, in_profile}[]`, `relevant_projects: {name, matched_skills: str[], mentioned_in_resume: bool}[]`, `missing_keywords: str[]`, `suggestions: {rule, message, evidence: str[]}[]`, `match_explanation: MatchExplanation` (skills are display names) |
| `InterviewPrep` | §10: `job_id`, `provider: "template"\|"llm"`, `sections: {category, title, questions: {id, category, text, skill?}[]}[]`, `prep_topics: {topic, reason, priority: "high"\|"medium"\|"low"}[]` |
| `IngestResult` | §11.5: `requested_source`, `source`, `fallback_used: bool`, `fetched`, `created`, `updated`, `duplicates`, `rejected` (ints), `errors: {index: int?, reason: str}[]` (≤ 50) |
| `Health` | `status: "ok"\|"degraded"`, `database: "ok"\|"unavailable"`, `version: str` |

## 9. Resume analysis (R8)

`ResumeService.analyze(user, job_id, resume_text | None)`.

### 9.1 Skill extraction

Produce two views of the resume text: `nfkc` (NFKC + whitespace collapse, case preserved) and `folded` (`nfkc.casefold()`). For every catalog canonical name and every alias (the "terms"), search with the regex `(?<![A-Za-z0-9+#.])` + `re.escape(term)` + `(?![A-Za-z0-9+#])` (whole-word/phrase, so `java` does not match `javascript`, `c` patterns only for `c++`/`c#`). Matches map to canonical names. Catalog = `CATALOG` keys ∪ `skills.normalized_name` from the DB ∪ the job's skills, so job-specific skills are detectable.

Ambiguous short terms: `skill_catalog.AMBIGUOUS_RESUME_TERMS` maps each lowercase term that is also common English or a common abbreviation to the exact casings accepted: `go → {Go, Golang}`, `golang → {Golang}`, `rest → {REST}`, `node → {Node}`, `js → {JS}`, `ts → {TS}`, `py → {PY}`, `ml → {ML}`, `dl → {DL}`, `r → {R}`, `c → {C}`. These terms are searched case-sensitively in `nfkc` for each accepted casing (same boundary regex); every other term is searched in `folded`. Multi-word terms containing an ambiguous word (`rest apis`, `node.js`) are not ambiguous and use the folded rule. Unit tests: `"go to market"` → no `go`; `"Built services in Go"` → `go`; `"built REST APIs"` → `rest apis`; `"the rest of the team"` → nothing; `"R and Python"` → `r`, `python`.

### 9.2 Outputs

- `matching_skills`: `(R ∪ P) ∩ resume_skills`, each `{skill, is_required}`.
- `missing_skills`: `(R ∪ P) − resume_skills`, each `{skill, is_required, in_profile}` (`in_profile` = in normalized profile skills).
- `relevant_projects`: profile projects whose technologies ∩ `R ∪ P` ≠ ∅, each `{name, matched_skills[], mentioned_in_resume}` (name appears in resume text, case-insensitive).
- `missing_keywords`: tokens from the job description (casefold, `[a-z][a-z0-9+#.]{2,}`, then trailing `.` characters stripped and tokens shorter than 3 characters dropped, so `"python."` → `python`), excluding a fixed English stop-word list and tokens present in the resume; keep tokens with frequency ≥ 2 or that are catalog skills; sort by frequency desc then alphabetically; max 15.
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
| `technical` | per required skill (alphabetical), 2 templates each; then preferred. If the job lists no skills: 3 generic templates using `{title}` (core concepts of the role, a recent technical problem solved, how you would ramp up in the first month) | 10 |
| `skill` | one "describe a time you used {Skill}" per required ∪ preferred skill, alphabetical; omitted (empty section is not returned) when the job lists no skills | 8 |
| `project` | per profile project sorted by casefolded name; template chosen by whether it uses job skills | 3 (fallback generic project question if no projects) |
| `hr` | fixed list | 5 |

Each question: `{id, category, text, skill?}` where `id = "{category}-{n}"`. `prep_topics`: missing required (`high`), matched required (`medium`), missing preferred (`low`), each `{topic, reason, priority}`, ordered by priority then name. Response: `{job_id, provider, sections[{category, title, questions[]}], prep_topics[]}`.

`InterviewService` picks the provider at startup: `LlmEnrichedInterviewProvider` only when `LLM_ENABLED=true` and `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` are set (R15.1); otherwise template. The LLM provider first builds the template result, then calls the OpenAI-compatible `POST {LLM_BASE_URL}/chat/completions` (httpx, 15 s timeout, `Authorization: Bearer`), asking for up to 5 extra technical questions as a JSON array of strings; valid strings (non-empty after trim, ≤ 300 chars, max 5) are appended to `technical` with ids continuing the section's numbering (`technical-{n+1}` …, `skill=null`) and `provider="llm"`; if no valid strings come back the result is the template result with `provider="template"`. The `technical` limit of 10 applies to template questions only. Any exception, non-2xx, timeout or parse failure → return the template result with `provider="template"` and log WARNING `llm_fallback reason=<type>` (R9.5, R15.3). The LLM is never used for scores or metrics (R15.2). Tests use `httpx.MockTransport`.

## 11. Job ingestion (R10)

### 11.1 Request

`IngestRequest`: `source` ∈ `fixture | remotive | arbeitnow | payload` (required); `fallback` bool default true; `limit` int 1–500 default 100; `format` ∈ `remotive | arbeitnow | normalized` (required iff `source=payload`); `payload` (object or list, required iff `source=payload`; ≤ 500 items after unwrapping). Violations → 422.

### 11.2 Sources (`sources.py`)

```python
JsonObject = dict[str, object]

@dataclass(frozen=True)
class RawBatch:
    format: RawFormat            # StrEnum: remotive | arbeitnow | normalized
    source: JobSource            # value stored in jobs.source for these items
    items: list[object]          # non-object items are rejected per item, not per batch

class JobSource(Protocol):
    name: str
    def fetch(self, limit: int) -> list[RawBatch]
```

- `RemotiveSource`: `GET https://remotive.com/api/remote-jobs?limit={limit}`; items at `jobs`.
- `ArbeitnowSource`: `GET https://www.arbeitnow.com/api/job-board-api`; items at `data`; truncated to `limit`.
- `PayloadSource`: wraps the request payload (unwraps `jobs`/`data` keys if an object).
- `FixtureSource`: reads `DATA_DIR/seed_jobs.json` and `DATA_DIR/ingest/*.json` (sorted filenames; files must be normalized format or carry a top-level `format`). No caller-supplied paths. It returns one batch per file: `seed_jobs.json` items keep `source="seed"` (so a fallback run updates the seeded rows by `(seed, external_id)` instead of creating duplicates); `ingest/*.json` items get `source="fixture"`. Remotive/Arbeitnow/Payload batches use `remotive`/`arbeitnow`/`payload`. A single `fetch` returns a one-element list for those sources.

Settled in 2.14: `limit` caps the total item count for every source (for fixtures, across files in order). A fixture file is either a list (normalized format) or an object with an optional `format` (default `normalized`) and its items under `jobs` or `data`; any other shape, an unknown `format`, invalid JSON, a file above `INGEST_MAX_BYTES` or an unreadable file makes the fixture source unavailable. Missing files are skipped (no files → an empty run).

`HttpFetcher` (shared by public sources): rejects URLs whose scheme is not `https`, whose host is not in `INGEST_ALLOWED_HOSTS` (exact match), or that carry credentials or a non-443 port, before any request (`disallowed_host`); `httpx.Client(timeout=INGEST_TIMEOUT_SECONDS, follow_redirects=False)` with an injectable transport for tests; requires 2xx (a 3xx is `http_status_3xx`, never followed) and a JSON content type (`application/json` or `*+json`, else `invalid_json`); rejects a declared `Content-Length` above `INGEST_MAX_BYTES` (5,000,000) and streams the decoded body, aborting once it exceeds the cap. Failures raise `SourceUnavailableError(reason)` with reasons `disallowed_host | timeout | network_error | http_status_<code> | too_large | invalid_json | unexpected_shape | read_error` (`read_error`: a fixture file could not be read).

### 11.3 Normalization (`normalizers.py`)

Each format has a normalizer `raw dict → JobCreate | Rejection(index, reason)`:
- HTML stripped with `html.parser`-based text extraction, entities unescaped, whitespace collapsed, truncated to 20,000 chars.
- Remotive: `external_id=str(id)`, `company=company_name`, `location=candidate_required_location or "Remote"`, `work_mode=remote`, `employment_type` from `job_type` (`full_time, part_time, contract, internship`; `freelance → contract`; other → `full_time`), `application_url=url`, `required_skills = tags` (normalized, max 15), `preferred_skills` = catalog skills found in the description not in required (max 10).
- Arbeitnow: `external_id=slug`, `work_mode = remote if remote else onsite`, `employment_type` from `job_types` (contains `intern`/`praktikum` → internship, `part` → part_time, `contract`/`freelance` → contract, else full_time), tags → required, description skills → preferred.
- Normalized: the seed format (§12), fields as in the jobs table; `deadline` (date) or `deadline_in_days` (int, resolved against `clock.today()`).
- Settled in 2.14: block-level tags (`p`, `div`, `br`, `li`, headings, table cells, …) separate words, inline tags (`b`, `a`, `span`) do not; `script`/`style` content is dropped. Other text fields (title, company, location) get the same HTML/whitespace cleaning but are not truncated (over 200 chars → rejected). Description skills use the §9.1 term rules against `CATALOG` names and aliases and are taken in normalized-name order. Arbeitnow items with an empty location and `remote=true` get `location="Remote"`. In the normalized format an explicit `deadline` wins over `deadline_in_days`; a non-integer `deadline_in_days` rejects the item. Rejection reasons are `field: message` pairs (≤ 300 chars) without input values.
- All formats: if the title contains the word `intern`/`internship`/`trainee` (whole words, so "Internal Tools" does not count), employment type becomes `internship`; `experience_level` inferred from title tokens when absent (`intern|internship|trainee → internship`, `graduate|entry|new grad → entry`, `junior|jr → junior`, `mid|intermediate → mid`, `senior|sr|lead|principal|staff → senior`, else null).
- `JobCreate` validation: title/company/location 1–200, `application_url` http(s) ≤ 500, ≤ 30 required and ≤ 30 preferred skills, salaries ≥ 0 and min ≤ max, currency `^[A-Z]{3}$`.

### 11.4 Dedupe and persistence (`service.py`)

`fingerprint = sha256(f"{n(title)}|{n(company)}|{n(location)}")` where `n` = casefold, non-alphanumerics → space, collapse, strip. For each valid item, in input order, within one transaction:
1. Existing job with same (source, external_id) → update mutable fields and skills; if the new fingerprint collides with a *different* job, skip the update and count `duplicates`. Else count `updated`.
2. Else existing job with the same fingerprint → count `duplicates` (skip).
3. Else insert → `created`. In-batch duplicates are caught by the same checks (fingerprints of earlier inserts are tracked in a set).
Rule 2 applies regardless of source, matching R10.5 and the global `UNIQUE(dedupe_fingerprint)`: an item from the same source with a different `external_id` but the same normalized title/company/location is a duplicate (integration test `test_ingest_same_source_new_external_id_same_fingerprint_counts_duplicate`). One `jobs_ingested` activity event is written per run. All fetching and validation happen before the first write, so a source failure never causes partial writes (R10.7).

### 11.5 Fallback

`IngestionService.ingest(user, req)`: try the requested source; on `SourceUnavailableError` from a public source (`remotive`/`arbeitnow`) with `fallback=true`, run `FixtureSource`, set `fallback_used=true`, `source="fixture"`, add `{index: null, reason: "<source>: <reason>"}` to `errors`, log WARNING. With `fallback=false`, or when the fixture/payload source itself fails (including the fallback run), raise `IngestionSourceUnavailableError` → 502 with `details={"source", "reason"}`. Item `index` values count items across all batches of the run in fetch order. `IngestResult`: `{requested_source, source, fallback_used, fetched, created, updated, duplicates, rejected, errors[≤50]}`. The MCP workflow (Kiro agent fetches with `mcp-server-fetch`, saves to `data/ingest/*.json` or posts `source=payload`) feeds the same pipeline; the app never depends on MCP (R10.9).

## 12. Seed data (R11)

Files: `data/seed_profile.json` (one user + skills), `data/seed_jobs.json` (≥ 30 jobs, normalized format, `source` forced to `seed`, `external_id` like `seed-001`, `deadline_in_days` relative), `data/seed_applications.json` (≥ 10, keyed by `job_external_id`, with `status`, `applied_days_ago`, `deadline_in_days`, `interview_in_days`, recruiter placeholders such as `recruiter@example.com`, notes, outcome; ≥ 6 distinct statuses). `SeedService.run()`:
1. Upsert catalog skills (`CATALOG` + all seed skills) by `normalized_name`.
2. Look up the user with `seed_key = 'demo'`. If absent, create it with `seed_key='demo'`, `email=DEMO_USER_EMAIL`, `name=DEMO_USER_NAME` and the profile from the file; if `DEMO_USER_EMAIL` already belongs to a user without a seed key, fail with exit 1 and an ERROR log rather than creating a conflicting user. If present, never overwrite it, even if its email or profile was edited (R11.2).
3. Ingest jobs through `IngestionService` with the normalized format (upsert by `seed`/`external_id`).
4. Only in the run that created the demo user (step 2), insert the seed applications (one per job, so no (user, job) pair repeats); write `application_created` events.
Exposed as `python -m app.cli seed` (exit 0 on success, 1 with a logged error on failure). Docker runs it after `alembic upgrade head` (R11.4).

Settled in 2.15:
- All three files are validated strictly (`app/schemas/seed.py`, unknown keys rejected) before the first write, and the whole run is one transaction (`IngestionService.stage_batches`, `ProfileService.apply` and `ApplicationService.insert` stage without committing). Any invalid file → `SeedDataError`, nothing written.
- `seed_profile.json` holds every `ProfileUpdate` field except `name`/`email` (those come from `DEMO_USER_NAME`/`DEMO_USER_EMAIL`). `seed_jobs.json` is a JSON list of normalized items with `deadline_in_days` only (no absolute `deadline`). `seed_applications.json` is a JSON list, one entry per `job_external_id`; `applied_days_ago` is required for submitted statuses, allowed for `Withdrawn`, forbidden for `Saved`/`Interested`; `interview_in_days` means 10:00 UTC that day.
- Step 4 is gated on user creation (instead of a per-(user, job) check) because an existing demo user's tracker belongs to the user: a re-seed must not re-create an application they deleted (R11.2). Those items are reported as `applications_skipped`.
- Re-seeding updates the seed job rows, so job deadlines move relative to the new seed day (R11.3); the seed run writes one `jobs_ingested` event like any ingestion.
- `python -m app.cli ingest --source {fixture,remotive,arbeitnow} [--no-fallback] [--limit N]` runs `IngestionService.ingest` as the demo user (exit 1 with `DEMO_USER_NOT_SEEDED` if the seed has not run). `data/ingest/remotive_sample.json` is a small Remotive-format fixture for the fallback path; its jobs do not share fingerprints with the seed jobs.

## 13. Configuration and identity (R13)

### 13.1 Settings (`app/core/config.py`, pydantic-settings, `.env` supported)

| Variable | Type / default | Notes |
|---|---|---|
| `APP_ENV` | `development` | `development | test | production` |
| `DATABASE_URL` | **required** | startup fails fast with a clear message if missing |
| `TEST_DATABASE_URL` | optional | tests use it if set, else in-memory SQLite |
| `CORS_ORIGINS` | `http://localhost:5173` | comma list of explicit http(s) origins (no `*`); see CORS below |
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

CORS (`app/main.py`): Starlette `CORSMiddleware` with `allow_origins=CORS_ORIGINS` (`DEFAULT_CORS_ORIGINS` when `create_app()` gets no settings), `allow_credentials=False` (no cookies or auth headers are used), methods `GET, POST, PUT, PATCH, DELETE, OPTIONS`, request headers `Content-Type, Accept, X-Demo-User, X-Request-ID`, `expose_headers=["X-Request-ID"]`. Stack order (outer → inner): `RequestIdMiddleware` → `CORSMiddleware` → `ServerErrorMiddleware` → `BodySizeLimitMiddleware` → routes, so preflights, 413s and 500s all carry `X-Request-ID` and, for allowed origins, the CORS headers the SPA needs to read the error envelope. Disallowed origins get no `Access-Control-Allow-Origin` (preflight 400). Tests: `backend/tests/api/test_cors.py`.

### 13.2 Current user

`get_current_user(request, session)`: header `X-Demo-User` (email, ≤ 254, compared lowercase) → that user or 401 `UNKNOWN_DEMO_USER`; no header → user with `seed_key = 'demo'` or 503 `DEMO_USER_NOT_SEEDED`. `DEMO_USER_EMAIL` is only the initial email used by the seed, so editing the profile email does not break default resolution (R13.2a). API test: `PUT /profile` with a new email, then `GET /profile` without a header → 200 with the new email; re-running the seed afterwards leaves exactly one user. The frontend sends no header by default. Documented as demo-only in README and `docs/api.md` (R13.5).

## 14. Error handling and logging

`app/core/errors.py`: `AppError(code, message, status_code, details)` with subclasses `NotFoundError(404)`, `ConflictError(409)` → `DuplicateApplicationError`, `InvalidStatusTransitionError`, `EmailTakenError`; `RequestValidationAppError(422)` → `ResumeEmptyError`; `PayloadTooLargeError(413)`; `UpstreamUnavailableError(502)` → `IngestionSourceUnavailableError`; `UnknownDemoUserError(401)`; `NotReadyError(503)` → `DemoUserNotSeededError`, `DatabaseUnavailableError`; `InternalError(500)`. Starlette `HTTPException`s (unknown route, wrong method, unparsable body) map to the envelope with codes `NOT_FOUND`, `METHOD_NOT_ALLOWED`, `BAD_REQUEST`, … and the standard status phrase as message (headers such as `Allow` kept). Handlers registered in `create_app` map: `AppError` → its envelope; `RequestValidationError` → 422 `VALIDATION_ERROR`; `sqlalchemy.exc.IntegrityError` → 409 `CONFLICT` (WARNING); `sqlalchemy.exc.OperationalError` → 503 `DATABASE_UNAVAILABLE` (ERROR); any other `Exception` → 500 `INTERNAL_ERROR`, "An unexpected error occurred." (ERROR with traceback and request id, never in the response).

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
| Health | DB check fails | yes | 503 `{"status":"degraded","database":"unavailable","version":"<app version>"}` (health body, not the envelope) | WARNING |

Logging: stdlib `logging`, format `%(asctime)s %(levelname)s %(name)s [%(request_id)s] %(message)s`; `RequestIdMiddleware` accepts a safe incoming `X-Request-ID` (`^[A-Za-z0-9-]{1,64}$`) or generates a UUID4, stores it in a context var and returns it (R12.5); one INFO access line per request (method, path, status, duration ms). Never log request bodies, resume text, emails of recruiters, or `LLM_API_KEY`.

## 15. Frontend design

### 15.1 Structure

```
frontend/
  index.html, vite.config.ts (incl. Vitest config), tailwind.config.ts, postcss.config.js, tsconfig.json, eslint.config.js, .prettierrc, .npmrc (save-exact)
  Dockerfile, nginx.conf
  src/main.tsx, src/App.tsx (BrowserRouter + AppProviders + AppRoutes)
  src/AppProviders.tsx         QueryClientProvider + ToastProvider (no router, so tests use MemoryRouter)
  src/AppRoutes.tsx            route table; pages lazy-loaded (React.lazy) inside AppShell's Suspense
  src/api/client.ts            fetch wrapper: base URL from VITE_API_BASE_URL, JSON, ApiError(code, message, status, details)
  src/api/{profile,jobs,applications,dashboard,recommendations,resume,interview,ingest,health}.ts
  src/types/api.ts             TS mirrors of backend schemas
  src/hooks/{useProfile,useJobs,useJob,useApplications,useApplicationsMeta,useDashboard,useRecommendations,useInterviewPrep,useHealth}.ts   queries
  src/hooks/{useUpdateProfile,useCreateApplication,useUpdateApplication,useDeleteApplication,useApplyToJob,useBookmarkJob,useHideJob,useAnalyzeResume,useIngestJobs}.ts   mutations
  src/hooks/useInvalidatingMutation.ts   shared mutation wrapper (invalidation map + caller callbacks)
  src/lib/{queryKeys.ts,queryClient.ts,format.ts,scoreBand.ts,enumOptions.ts,jobFilters.ts,markApplied.ts}
  src/hooks/{useDebouncedValue,useJobListSearchParams}.ts   UI helpers (no server state)
  src/components/layout/{AppShell,Sidebar,TopBar,PageHeader,PageLoading}.tsx, navigation.ts (NAV_ITEMS, sectionTitle)
  src/components/ui/{Button,IconButton,Spinner,Card,Badge,Field,FieldError,TextField,TextArea,Select,Checkbox,Dialog,Skeleton,SkeletonBlock,EmptyState,ErrorState,Tabs}.tsx
  src/components/ui/{buttonStyles.ts (buttonClasses for Links styled as buttons), useFieldIds.ts}; src/lib/classNames.ts (cx)
  src/components/ui/toast/{ToastProvider.tsx,toastContext.ts}; src/hooks/{useToast,useMediaQuery}.ts; src/lib/toastMessages.ts
  src/components/match/{MatchScoreRing,MatchExplanationPanel,FactorBreakdown}.tsx
  src/components/jobs/{JobCard,JobFilters,Pagination}.tsx   (JobsPage renders the list)
  src/components/jobs/{JobActions,JobFlags,JobSkills,SkillList,DeadlineText,JobFacts,ApplicationSummary}.tsx   shared by JobCard and JobDetailPage
  src/lib/url.ts (safeExternalUrl); src/hooks/useDocumentTitle.ts
  src/components/applications/{ApplicationsTable,StatusFilter,KanbanBoard,KanbanColumn,KanbanCard,MoveToMenu,ApplicationDialog,DeleteApplicationDialog}.tsx
  src/lib/{applicationTransitions.ts (allowedTargets, canMove, statusChoices — read meta only), applicationForm.ts (datetime-local ↔ ISO, create body, PATCH diff, field errors)}
  src/components/dashboard/{StatCards,ChartFigure,StatusBreakdownChart,ApplicationsOverTimeChart,UpcomingDeadlines,RecentActivity}.tsx (3.10); {ScoreDistributionChart,TopRecommendations}.tsx (4.9)
  src/lib/{dashboard.ts (formatPercent, dueInText, formatWeekStart, hasAnyCount, isDashboardEmpty, activity/deadline labels — display only), chartColors.ts (hex mirrors of tokens for Recharts)}
  src/pages/{DashboardPage,JobsPage,JobDetailPage,ApplicationsPage,ResumePage,InterviewPage,ProfilePage,NotFoundPage}.tsx
  tests/**/*.test.tsx, tests/setup.ts
```

Routes: `/` → redirect `/dashboard`; `/jobs`; `/jobs/:jobId`; `/applications?view=table|board`; `/resume?jobId=`; `/interview/:jobId` (and `/interview` with a job picker); `/profile`; `*` → NotFound (inside the shell, link back to `/dashboard`). React Router v7 future flags (`v7_startTransition`, `v7_relativeSplatPath`) are on.

Shell (`AppShell`): skip link → `#main-content` (`<main tabIndex=-1>`); `TopBar` shows the section title (also `document.title` = `<section> · InternPilot AI`) and a "Demo user · not real authentication" notice (R13.5); `Sidebar` is a `<nav aria-label="Primary">` of `NavLink`s (`aria-current="page"`, child routes keep their section active). At ≥ `md` (768 px, via `matchMedia`) the sidebar is a sticky left column; below it the sidebar is hidden behind a "Menu" button (`aria-expanded`, `aria-controls`) and opens as a panel under the top bar that closes on link click or Escape (focus returns to the button).

Toasts (R14.3): `useToast()` → `success | info | error(message)`, `fromError(error)` (uses `toastErrorMessage`: the `ApiError` envelope message; `INVALID_STATUS_TRANSITION` appends "Allowed moves: …"; non-`ApiError` → generic message), `dismiss(id)`. Success/info render in a `role="status"` `aria-live="polite"` region, errors in a `role="alert"` region; each toast has a text variant label (not color alone) and a "Dismiss notification" button; auto-dismiss after 5 s (errors 10 s), at most 3 visible (oldest dropped); durations and max are `ToastProvider` props.

UI kit (R14.2, R14.4): native elements only; focus styling comes from the global `:focus-visible` rule. `Button` (variants `primary|secondary|ghost|danger`, sizes `sm|md`, `type` defaults to `"button"`, `isLoading` → disabled + `aria-busy` + spinner + sr-only "(loading)"; ref-forwarding); `IconButton` requires `aria-label`. `TextField`/`TextArea`/`Select`/`Checkbox` render a `<label htmlFor>` (id from `useId` unless given), an optional hint and an error (`FieldError`, visible "Error:" prefix), wired through `aria-describedby` and `aria-invalid`; `required` shows a text "(required)" marker plus the native attribute. `Dialog` is a manual modal in a portal (`role="dialog"`, `aria-modal`, labelled by its title, described by its description): focus moves to `initialFocusRef` or the panel on open, Tab/Shift+Tab are trapped, Escape and the close button close it, backdrop click closes unless `closeOnBackdropClick={false}`, body scroll is locked, and focus returns to the previously focused element. `Skeleton` is a `role="status"` region with an sr-only label ("Loading…" by default) around `aria-hidden` `SkeletonBlock`s; `EmptyState` has a title, description and a next-step `action`; `ErrorState` is `role="alert"` with the `toastErrorMessage` text and a Retry button calling `onRetry`. `Tabs` follows the WAI-ARIA tabs pattern with automatic activation (roving tabindex, ArrowLeft/ArrowRight wrap, Home/End), is controlled (`value`/`onChange`, so `?view=` can drive it), and renders only the selected panel's content.

### 15.2 Behavior

- Job list filters/sort/page live in the URL (`useSearchParams`); search input debounced 300 ms.
  Settled in 3.7: `useJobListSearchParams` reads the URL through `parseJobListParams` and writes it through `serializeJobListParams` (`src/lib/jobFilters.ts`). Its setter takes params or an updater `(current) => next` (like `setState`); updaters see writes not rendered yet, so two fields committing before the next render (e.g. a debounced skills commit and Enter in Location) both reach the URL. `JobFilters` only emits updaters. Parsing is lenient: unknown keys and invalid values (enums, flags other than `true`, page < 1, page_size outside 1–100) are dropped rather than sent to the backend. Both sides go through `normalizeJobListParams` (text trimmed and capped at 100/120 chars, multi-values de-duplicated in canonical enum order, skills trimmed and de-duplicated case-insensitively, ≤ 10 × ≤ 50 chars, defaults omitted: page 1, page_size 20, `false` flags, an `order` equal to the key's default or without a `sort`), so `parse(serialize(x)) = normalize(x)`. Serialized key order: `q, employment_type*, work_mode*, experience_level*, location, source, skills (comma list), bookmarked, include_hidden, sort, order, page, page_size`. Until 4.9 the UI omits `min_score` and `sort=match_score` (dropped when parsed); the sort select offers "Default order" (no `sort` sent) plus the five non-score keys, and the order toggle is disabled without a key. Search, location and skills commit after a 300 ms pause or on Enter; any filter or sort change resets the page to 1. "Clear filters" removes search and filters but keeps sort and page size.
  Job cards: salary via `formatSalary` (`Intl.NumberFormat` `en-US`, currency + "per year/month/hour", "From"/"Up to" for open ranges, plain number for an unknown currency code, "Salary not listed"); deadline as "Mar 15, 2025 · 12 days left" from calendar-date arithmetic against the browser's local date (display only). Required skills are solid bold badges after a visible "Required:" label, preferred ones dashed after "Preferred:", each with an sr-only prefix. Bookmark is a toggle button with a fixed name and `aria-pressed`; Hide/Unhide; "Mark as applied" is disabled (with the reason as `title`) when the status is `Applied` or `/applications/meta` says the status cannot move to `Applied` (`markAppliedState`); without meta it stays enabled and a 409 surfaces as a toast. The result count is a polite live region. Empty results show "Clear filters" when filters are active, otherwise the CLI import command (there is no import button in the UI); a page past the end offers "Go to the first page".
- Job detail (settled in 3.8): `:jobId` must match `^[1-9]\d*$` and be a safe integer, otherwise the page shows "Job not found" (h1) with an EmptyState and a "Back to jobs" link and makes no request; a 404 `ApiError` shows the same state. Loading shows a skeleton under an h1 "Job details"; other errors show ErrorState with Retry. Loaded: h1 = job title (`document.title` = `<title> · Jobs · InternPilot AI`, restored on unmount), company · location, `JobFlags` badges (status, Bookmarked, Hidden, plus a text note when hidden), `JobActions` (same buttons and toasts as JobCard; hide toasts "Job hidden from lists and recommendations"), and "Apply on company site" only when `safeExternalUrl` (absolute `http:`/`https:` only) accepts `application_url` (`target="_blank"`, `rel="noopener noreferrer"`, sr-only "(opens in a new tab)"; otherwise a "No valid application link" note). Cards: Overview (`JobFacts`: work mode, employment type, experience level, minimum education, salary, deadline with days left, source, discovered timestamp), Skills (shared `SkillList` badges), Description (plain text, `whitespace-pre-line`, React escaping only), and "Your application": `ApplicationSummary` (status badge, applied on, application deadline, interview via `formatDateTime` in the viewer's time zone with the zone name, recruiter name + `mailto:` link, notes, outcome, "Not set" for empty values, link to `/applications`) or "Not tracked yet" with "Save to tracker" (`POST /applications` `{job_id, status: 'Saved'}`; 409 shows the envelope message). Mark as applied lives in the action bar in both cases. The match score/explanation panel is added in 4.9.
- Mutations invalidate: application changes → `applications`, `dashboard`, `jobs`, `recommendations`, `job`; profile save → everything match-dependent; bookmark/hide → `jobs`, `job`, `dashboard`, `recommendations`. No optimistic updates for status moves (server is the source of truth for transitions); the card shows a pending state.
- Query keys (`src/lib/queryKeys.ts`) are hierarchical: `['profile']`; `['jobs','list',params]` / `['jobs','detail',id]` (`jobs` = list prefix `['jobs','list']`, `job` = `['jobs','detail']`); `['applications','list',params]`, `['applications','meta']`; `['dashboard']`; `['recommendations',{limit}]`; `['interview',jobId]`; `['health']`; `['resume']` is the resume-analysis mutation key (a `POST` compute, not cached). `INVALIDATION_MAP` (kind → prefixes) + `invalidateFor(queryClient, kind)`:
  - `profileUpdated` → profile, jobs, job, recommendations, dashboard, interview (R1.6).
  - `applicationChanged` (create, PATCH, delete, mark applied) → applications, jobs, job, recommendations, dashboard (R6.3). `applications/meta` is static and never invalidated.
  - `jobStateChanged` (bookmark/hide set or unset) → jobs, job, recommendations, dashboard.
  - `jobsIngested` → jobs, job, recommendations, dashboard, applications (job summaries may be updated), interview (uses job title/skills).
  - Resume analysis invalidates nothing (no server state changes).
- Mutation hooks wrap `useInvalidatingMutation`: on success they await the invalidation (so `isPending` lasts until dependent queries have refetched), then call the caller's optional `onSuccess(data, variables)`; `onError(error, variables)` runs without invalidation. Toasts are attached by callers.
- `createQueryClient()` (`src/lib/queryClient.ts`): `staleTime` 30 s, `refetchOnWindowFocus: false` (in-app changes refresh via the map; the single demo user has no other writers except CLI ingestion), query retries only for `ApiError` status 0 (network) or ≥ 500, at most 2 retries with 500 ms × 2ⁿ backoff capped at 5 s; 4xx and non-`ApiError` failures are final; mutations never retry. Query functions forward TanStack's `AbortSignal` to `src/api/*`; `useJob`/`useInterviewPrep` are disabled until the id is a positive integer; `useJobs` keeps the previous page as placeholder data while the next loads.
- Kanban: 8 columns from `/applications/meta`; cards are `draggable`; drop targets not in `transitions[current]` show a not-allowed style and are ignored with an info toast; each card has a "Move to…" menu button (keyboard operable, lists only allowed targets).
  Settled in 3.9: `/applications?view=table|board` (missing/invalid → table; switching tabs writes `view` with `replace`). The table view has an any-of status filter (checkboxes in meta order, written as repeated `status` params in canonical order; unknown values are dropped before the request); the board always loads every status. Table: `<caption>`, columns Job (link to `/jobs/:id`, row header), Company, Status (text badge), Applied, Deadline (`application.deadline ?? job.deadline` with days left), Interview (viewer's zone), Updated, Actions (a labelled per-row status `<select>` with the current status plus `statusChoices`, Edit, Delete); server order (updated desc). Board: each column is a `<section>` region named "`<Status>`, n applications" with a list of `<article>` cards (title link, company · location, deadline, interview). During a drag every column shows a text cue next to its style: "Drop here" (allowed; `dragover` is accepted), "Not allowed" (`dropEffect="none"`, a drop makes no request and shows an info toast with the allowed moves), "Current column". "Move to…" is a WAI-ARIA menu button (Enter/Space/ArrowDown open on the first item, ArrowUp on the last; ArrowUp/Down wrap, Home/End, Escape closes and returns focus, Tab leaves, outside click closes). A move PATCHes `{status}`; while it is pending the card shows "Moving…" with `aria-busy` and all move controls are disabled; success toasts and updates an sr-only `role="status"` announcer ("Moved X to Interview"); a 409 toasts the envelope message (with allowed moves) and the card stays put. `allowedTargets`/`canMove`/`statusChoices` read `meta` only; there is no transition table in the frontend (`APPLICATION_STATUSES` in `enumOptions.ts` only validates `?status=`).
  Dialogs: "Add application" lists jobs from `GET /jobs?sort=title&page_size=100` (the page-size cap; the hint says when more exist and points to "Save to tracker" on the job page) excluding jobs that already have an application; status may be any value (meta order). Edit shows notes, applied on, deadline (`type=date`), interview (`datetime-local` in the viewer's zone → ISO UTC without milliseconds; shown back via `isoToDateTimeLocal`), recruiter name/email and outcome; status is not editable there. Create omits blank optional fields; edit PATCHes only changed fields (text compared trimmed, interview compared as the displayed local value), `null` for a cleared nullable field, and makes no request (info toast) when nothing changed. 422 errors show inline and focus the first invalid field (paths not shown in the form appear in an alert list); 409 `DUPLICATE_APPLICATION` shows inline on Job and as a toast. Delete asks for confirmation naming the job and company, with focus on Cancel and a danger "Delete application" button.
- Dashboard (settled in 3.10): one `GET /dashboard` via `useDashboard`; the page only formats backend values (no metric math, no fallback numbers). Loading → skeleton; error → ErrorState with Retry; `isDashboardEmpty` (`total_jobs_discovered = 0`, `applications_submitted = 0` and every `status_breakdown` count 0) → a page-level EmptyState with "Complete your profile" (`/profile`) and "Browse jobs" (`/jobs`). Otherwise, in order: `StatCards` (a `<dl>`: Total jobs discovered, Matching jobs with the "not hidden, score ≥ 60" hint, Applications submitted, Interviews scheduled, Offers received, Response rate as `value.toFixed(1)%`; some cards link to `/jobs`, `/applications`, `/applications?view=board`); `StatusBreakdownChart` (horizontal Recharts bars in the backend's status order) and `ApplicationsOverTimeChart` (weekly bars, x-axis "Mar 3", tooltip/table "Week of Mar 3, 2025"); `UpcomingDeadlines` (≤ 8 rows: title link to `/jobs/:job_id`, company, `<time>` date, "Due today/tomorrow/in n days" from `days_left`, text badge "Application"/"Bookmark"); `RecentActivity` (`<ol>`: type label badge, `<time dateTime>` via `formatDateTime`, message). Charts use `ChartFigure`: a `role="img"` wrapper whose `aria-label` lists every value, a visible caption, and a "Show data table" toggle (`aria-expanded`/`aria-controls`) revealing a table with the same numbers. Colors come from `CHART_COLORS` (unit-tested against `tailwind.config.ts`). A chart whose counts are all 0 and empty lists show section EmptyStates with a next action. Tests replace `ResponsiveContainer` with a fixed-size clone (jsdom has no layout/ResizeObserver). Task 4.9 adds the score distribution chart and top recommendations as further sections (data already in `Dashboard`). Until the backend lands (4.6) the live page shows the ErrorState.
- `ApiError` messages surface in toasts; 409 transition errors show the allowed targets.
- Design tokens (Tailwind `theme.extend`): `ink` neutrals (slate), `pilot` primary (teal `#0F766E` family), `signal` accent (amber `#B45309`), semantic `success/warning/danger`; font Inter with system fallback; radius `lg`; score bands ≥ 80 `success`, 60–79 `pilot`, 40–59 `warning`, < 40 `danger`, always alongside the number (R14.5). Text tokens meet 4.5:1 on their backgrounds. Settled values (`frontend/tailwind.config.ts`): `ink` = Tailwind slate 50–950; `pilot` = teal 50–950 with `DEFAULT` `#0F766E` (700); `signal` = amber 50–900 with `DEFAULT` `#B45309` (700); `success` `#15803D`, `warning` `#B45309`, `danger` `#B91C1C` (each with 50/100/500/700/800); `borderRadius.DEFAULT` 0.5rem; focus = 2px `outline-focus` (`#0F766E`) with 2px offset on `:focus-visible` (global in `src/index.css`). Text uses the 700+ shades of colored tokens (≥ 4.5:1 on white/ink-50) and ink-600+ for neutrals; 500/600 shades are for fills, borders and icons only. Inter is referenced by name only (system-font fallback; no web-font download, so the app works offline).
- `MatchScoreRing`: SVG circle with `role="img"` and `aria-label="Match score 87 out of 100"`, visible `87/100`; panel title reads `MATCH SCORE: 87/100`.

## 16. Testing strategy

| Level | Location | What |
|---|---|---|
| Unit | `backend/tests/unit/` | normalization, each factor rule and reason template, rounding, state machine, dashboard `compute_metrics`, resume extraction/suggestions, interview templates, normalizers, fingerprint, HttpFetcher guards (MockTransport) |
| Integration | `backend/tests/integration/` | repositories + services on a real session (SQLite default, Postgres via `TEST_DATABASE_URL`): ingestion dedupe/update/fallback, seed idempotency, application uniqueness and check constraint, cascade |
| API | `backend/tests/api/` | `TestClient` for every endpoint: success shapes, error envelope, 404/409/422/413, request id header |
| Property | `backend/tests/property/test_matching_properties.py`, `test_application_status_properties.py` | P1–P6 (§17) with a registered Hypothesis profile (`max_examples=200`, `derandomize=True`, `deadline=None`) |
| Frontend | `frontend/tests/` | `MatchScoreRing`, `MatchExplanationPanel` (+/- prefixes), `KanbanBoard` (allowed moves only, Move-to menu by keyboard), `JobFilters` URL sync, `api/client` error parsing, Dashboard empty state |

Dates are controlled with `FixedClock` injected via `get_clock` override. No test touches the network. Frontend: `tests/setup.ts` blanks `VITE_API_BASE_URL` and replaces `fetch` with a rejecting stub before every test (only `tests/api/client.test.ts` installs its own); page tests that show "days left" pin the date with `vi.useFakeTimers({ toFake: ['Date'] })` + `vi.setSystemTime(new Date(2025, 0, 20, 12))` (local noon, so the day is the same in every time zone).

Test database bootstrap: `DATABASE_URL` is required at runtime, so `backend/tests/conftest.py` sets `os.environ["DATABASE_URL"]` at import time — before any `app` module is imported — to `TEST_DATABASE_URL` if set, else `sqlite+pysqlite://`. The SQLite engine uses `StaticPool` and `connect_args={"check_same_thread": False}` so the in-memory database is shared by the `TestClient` thread. A plain `pytest` therefore runs with no `.env`. Integration tests include a SQLite round-trip of an aware `interview_date` compared with `FixedClock.now()` (UTCDateTime, §4). Coverage gates: backend ≥ 80% lines, `app/services/matching` ≥ 95% (`pytest --cov`); frontend ≥ 60% lines for `src/components` and `src/lib`.

## 17. Correctness properties ↔ requirements

| Property | Statement (Hypothesis strategy) | Requirements | Test |
|---|---|---|---|
| P1 Score bounds | For arbitrary `MatchProfile`/`MatchJob` (random skill strings incl. catalog skills, aliases, unicode; random enums incl. None; 0–20 projects): `0 ≤ score ≤ 100`, `isinstance(score, int)`, each factor `0 ≤ points ≤ weight`, `score == floor(Σ points + 1/2)`, exactly 8 factors. | R3.1, R3.3, R3.4, R4.1, R4.2 | `test_p1_score_is_bounded` |
| P2 Monotonicity | For any p, j and any `s ∈ j.required ∪ j.preferred`: `score(p + s) ≥ score(p)`. For any `s` with `normalize_skill(s) ∉ R ∪ P`: result unchanged. | R3.5, R3.6 | `test_p2_adding_matching_skill_never_lowers_score`, `test_p2_adding_unrelated_skill_changes_nothing` |
| P3 Duplicates | For p and a variant whose skills are p's skills plus duplicates, case/whitespace variants, edge-punctuation-wrapped variants (`" React ,"`, `"(React)"`, `"React."`) and aliases: identical `MatchResult`. | R3.2, R3.7 | `test_p3_duplicate_skills_have_no_impact` |
| P4 Missing skills | For any p, j: every `r ∈ R − S` is in `missing_required_skills` and not in `matched_required_skills`; required points `= 35·|R∩S|/|R|`; if `S ∩ R = ∅ ≠ R` then required points = 0 (same for preferred). | R3.8, R3.9, R4.3 | `test_p4_missing_required_skills_get_no_credit` |
| P5 Determinism | `compute_match(p, j) == compute_match(p, j)` and equals the result for p, j with all tuples permuted. Strategies deliberately include project names that collide after casefold with different technologies (`"Chat App"`/`"chat app"`) and target roles equal after casefold but different in original text (`"Backend Engineer"`/`"backend engineer"`), plus stop-token-only roles. | R3.10, R3.11, R4.6 | `test_p5_match_is_deterministic_and_order_independent` |
| P6 Status validity | For any start status and any sequence of target strings (valid statuses and arbitrary text): after each step the status is exactly one member of `ApplicationStatus`; invalid targets raise and leave it unchanged; the Pydantic schema rejects non-members; a service-level stateful test (Hypothesis `RuleBasedStateMachine` over `ApplicationService` on SQLite) checks the stored row too. | R5.2, R5.4, R5.5 | `test_p6_application_always_has_one_valid_status` |

Each test docstring cites its property and requirement IDs. `pytest backend/tests/property -v` runs them all. The P6 service state machine overrides the profile to 50 examples × 20 steps because each example builds a fresh SQLite schema.

## 18. Docker and local run

`docker-compose.yml`:
- `db`: `postgres:16-alpine`, env from `POSTGRES_*`, named volume `pgdata`, healthcheck `pg_isready`, `ports: ["127.0.0.1:${POSTGRES_PORT:-5432}:5432"]` (loopback only, for host-run backends and `TEST_DATABASE_URL`; documented in README).
- `backend`: build `./backend` (`python:3.12-slim`, non-root user `app` uid 10001, `DATA_DIR=/data`, `EXPOSE 8000`, `HEALTHCHECK` via stdlib `urllib` on `/api/health`, so 503 degraded = unhealthy), `environment.DATABASE_URL: postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}` (overrides the localhost URL from `.env`, which is for host-run backends only; inside the container `localhost` is the container itself; `.env` is not passed as `env_file`), `DATA_DIR=/data`, `./data:/data:ro`, `depends_on: db (service_healthy)`, other §13.1 settings passed through with the §13.1 defaults (`APP_ENV` defaults to `production`), entrypoint `docker-entrypoint.sh` (`set -eu`) → `alembic upgrade head` (retried up to `MIGRATE_MAX_ATTEMPTS`=10 times, `MIGRATE_RETRY_SECONDS`=3 apart, then exit 1), `python -m app.cli seed` (exit 1 stops the container), `exec uvicorn --factory app.asgi:build_app --host 0.0.0.0 --port 8000`; port `127.0.0.1:${BACKEND_PORT:-8000}:8000` (loopback only, because the demo identity is not authentication). `app.asgi.build_app()` = `create_app(get_settings())`, so `LOG_LEVEL` applies and a missing `DATABASE_URL` fails at startup. No `restart` policy: a failed migrate/seed leaves the container exited with its log instead of restart-looping.
- `frontend`: build `./frontend`, multi-stage. Stage 1 `node:22.23.3-alpine` as user `node`: `npm ci`, then `npm run build` with build arg `VITE_API_BASE_URL` (compose passes `${VITE_API_BASE_URL:-http://localhost:8000/api}`; Vite inlines it into the bundle, so it is public, never a secret, and changing it needs a rebuild). Stage 2 `nginxinc/nginx-unprivileged:1.27.5-alpine` (non-root uid 101, listens on 8080) serves `dist/` with `frontend/nginx.conf` as `conf.d/default.conf`: SPA fallback `try_files $uri $uri/ /index.html`, `/assets/` (content-hashed) `Cache-Control: public, max-age=31536000, immutable` and 404 when missing, `index.html` `no-cache`, gzip for text assets, `server_tokens off`, headers `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `X-Frame-Options: DENY` (no CSP). `HEALTHCHECK` `wget -q --spider http://127.0.0.1:8080/`. `depends_on: backend (service_healthy)`; port `127.0.0.1:${FRONTEND_PORT:-5173}:8080` (loopback only), so the browser origin stays `http://localhost:5173`, which is the default `CORS_ORIGINS`; changing `FRONTEND_PORT` requires changing `CORS_ORIGINS` too. The browser calls the backend directly at `VITE_API_BASE_URL` (no nginx proxy). `frontend/.dockerignore` excludes `node_modules`, `dist`, `coverage`, `tests` and `.env*`.
Secrets come from `.env` (gitignored). `POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB` use `${VAR:?…}` (compose refuses to start without them; no password literal in the file and they must be URL-safe because they are spliced into `DATABASE_URL`); everything else uses `${VAR:-default}` matching `.env.example`. `.gitattributes` keeps `*.sh` LF and the Dockerfile also strips CR from the entrypoint. `backend/.dockerignore` excludes `.env*`, virtualenvs, caches, `tests/` and dev requirements.

Local dev: `python -m venv .venv`, `pip install -r requirements-dev.txt`, `alembic upgrade head`, `python -m app.cli seed`, `uvicorn --factory app.asgi:build_app --reload`; `npm ci`, `npm run dev`. Exact commands live in README.

## 19. Spec review responses (docs/reviews/spec-review.md)

All 23 findings were addressed; none were backlogged or rejected.

| # | Severity | Response |
|---|---|---|
| 1 | HIGH | Added `users.seed_key` (§4.1, §4.2); seed and default-user resolution use `seed_key='demo'` (§12, §13.2); new R13.2a, R11.2 and R13.2 updated; API test specified in §13.2. |
| 2 | MEDIUM | §5.1 step 3 now loops until stable; idempotence unit + Hypothesis checks; P3 strategy includes punctuation variants (§17). |
| 3 | MEDIUM | Usable roles `U` defined, both neutral cases ratio 1/2, two separate reason templates (§5.3, §5.4). |
| 4 | MEDIUM | Project groups by casefolded name with union of shared skills and smallest display name; total-order role tie-break; P5 strategies include collisions (§5.3, §5.4, §5.6, §17). |
| 5 | MEDIUM | R10.5 reworded to "any existing job with a different (source, external_id)"; same-source integration test named in §11.4. |
| 6 | MEDIUM | One health body everywhere (R12.2 exemption, R12.6, §8, §8.3, §14). |
| 7 | MEDIUM | 201 only when created, 200 for transition/already Applied, 409 otherwise (R2.10, R2.11, §6 `MarkAppliedResult`, §8). |
| 8 | MEDIUM | `AMBIGUOUS_RESUME_TERMS` matched case-sensitively in canonical casings (§9.1, R8.3); unit tests listed. |
| 9 | MEDIUM | Compose sets the backend `DATABASE_URL` to the `db` host (§18); `.env.example` comments the localhost URL as host-only. |
| 10 | MEDIUM | `UTCDateTime` type decorator for every timestamp column (§4, §4.2, NFR2); SQLite round-trip test (§16). |
| 11 | MEDIUM | New §8.3 with exact response schemas. |
| 12 | NIT | Exact on `Fraction`s; JSON within 0.01 (R4.2, §5.3). |
| 13 | NIT | `seed_jobs.json` keeps `seed`, `ingest/*.json` uses `fixture` (§11.2). |
| 14 | NIT | Location reason now "matches your location or preferred locations" (§5.4). |
| 15 | NIT | `EMAIL_TAKEN`, `CONFLICT` added to coding-standards; `InvalidStatusTransitionError` used everywhere (§6). |
| 16 | NIT | `GET /applications` exception documented with a 500 cap (§8, coding-standards). |
| 17 | NIT | tasks.md: score display moved from 3.7 to 4.9; marker legend added. |
| 18 | NIT | conftest sets `DATABASE_URL` before importing the app (§16). |
| 19 | NIT | Generic technical fallback for jobs without skills; LLM ids continue `technical-{n}` (§10). |
| 20 | NIT | Whitespace-only resume = empty (R8.7, §8.1); trailing `.` stripped from keywords (§9.2); skills normalizing to `None` → 422 (R1.3, §8.1). |
| 21 | NIT | `JsonObject = dict[str, object]`, typed `RawBatch` (§11.2). |
| 22 | NIT | `db` published on `127.0.0.1:5432` only (§18). |
| 23 | NIT | `job_id` added to R4.1. |
