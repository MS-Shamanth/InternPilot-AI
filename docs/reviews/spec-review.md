# Spec review: InternPilot AI (internship-intelligence)

Verdict: **CHANGES_REQUESTED** — 1 HIGH, 10 MEDIUM, 12 NIT.

## Scope

Reviewed in full: `docs/project-brief.md` (the binding brief, acceptance sections 0, 4, 5, 7, 12, 13), `.kiro/specs/internship-intelligence/{requirements,design,tasks}.md`, and the five steering docs under `.kiro/steering/`. Spot-checked `backend/pyproject.toml`, `backend/tests/conftest.py` and `.env.example` to verify design claims. No builds or tests were run (documentation review).

## Coverage against the brief

| Brief section | Result |
|---|---|
| §4 Specs: EARS, numbered, testable; the four example criteria; PBT-derivable requirement; design with architecture, data model, weighted algorithm, API, properties ↔ requirements; phased tasks with requirement IDs | Met. R1–R15 are EARS and numbered; R3.1, R3.2, R2.10 and R3.5 contain the brief's four example criteria verbatim; design §5 has exact weights, §17 maps P1–P6; tasks.md follows the 8 commit phases and cites R/§ IDs. |
| §5 Steering: five files, required contents, Kiro front matter | Met. All five files start with `inclusion: always` and cover every listed topic (see per-file summary). |
| §7 PBT: six properties, named after property, cite requirement IDs, `pytest backend/tests/property -v` | Met at spec level. P1–P6 in requirements and design §17; test names `test_p<n>_...`; the brief's P3 ("duplicating doesn't increase") is strengthened to "identical result", which implies it. |
| §12 Database: all tables/columns, `unique(source, external_id)`, fingerprint, `unique(user_id, job_id)`, status check | Met (design §4.1). `activity_events` and `user_job_states` added with justification. Two portability/identity defects found (findings 1, 10). |
| §13 API: every listed endpoint + bookmark/hide + health, envelope | Met (design §8). Contract gaps in findings 6, 7, 11. |
| §0 Binding decisions relevant to specs (phases/commits, checklist ticking, Docker/Postgres, demo identity, pinned deps) | Mostly met; Docker connectivity gap in finding 9. |

The specs are concrete and implementation-ready, not boilerplate. The blocking items are specific correctness or contract defects that would produce bugs, failing property tests or a broken demo.

## Findings

### HIGH

**1. Editing the profile email breaks demo identity and seed idempotency** — requirements R1.2, R13.2, R11.2; design §8.1, §12 step 2, §13.2.
`PUT /profile` allows changing `email` (409 `EMAIL_TAKEN` exists), but `get_current_user` resolves the default user by `email == DEMO_USER_EMAIL` and the seed creates the demo user "only if absent" by email. After the user edits their email (a natural demo action), every header-less request returns 503 `DEMO_USER_NOT_SEEDED`, the next `docker compose up` seeds a second demo user, and the edited profile is orphaned. This also violates R11.2 ("SHALL NOT overwrite user-edited profile data") in spirit and breaks brief §16 demo mode.
Fix: add `users.seed_key varchar(32) null unique`; seed sets `'demo'` and checks existence by `seed_key`; header-less `get_current_user` loads `seed_key='demo'` or returns 503; `DEMO_USER_EMAIL` is only the initial email. Add R13.2a: "WHEN the demo user changes their email THE SYSTEM SHALL continue to resolve them as the default user." Add an API test: change email, then `GET /profile` without header → 200.

### MEDIUM

**2. `normalize_skill` is not idempotent; trailing whitespace survives** — design §5.1 (affects R3.2, R3.7, P3).
Whitespace is stripped in step 2, before punctuation in step 3, so `" React ,"` → `"react "` and `"( React )"` → `" react "`, which never match `react`. P3 fails as soon as strategies include punctuation.
Fix: step 3 becomes "repeat {strip whitespace; strip leading/trailing chars in the set; strip one trailing `.`} until unchanged, then alias lookup." Add `test_normalize_skill_is_idempotent` and a Hypothesis check `normalize_skill(normalize_skill(x) or "") == normalize_skill(x)`; add punctuation-wrapped variants to the P3 strategy.

**3. Role similarity divides by zero for stop-token-only roles** — design §5.3 factor 3.
"Usable target roles" is undefined. A target role such as `"Intern"` or `"Senior"` yields `tok(t) = ∅`, so `|tok(t) ∩ tok(title)| / |tok(t)|` is undefined.
Fix: `U = {t ∈ target_roles : tok(t) ≠ ∅}`. `U = ∅` or `tok(title) = ∅` → ratio 1/2; else max over `t ∈ U`. Split the neutral reason: `U = ∅` → "Add target roles to your profile to improve role matching"; `tok(title) = ∅` → "Job title has no comparable role terms".

**4. Reason text depends on input order (violates P5 / R3.10)** — design §5.3 tie-break, §5.4 projects row, §5.6.
Projects are de-duplicated "by casefolded name" but two projects `"Chat App"` and `"chat app"` with different technologies make relevance, the shared skill and the displayed `{name}` depend on which comes first. Same for target roles that are equal after casefold but differ in original text (`{role}` in the reason). P5 asserts explanation equality under permutation and will find this.
Fix: group projects by casefolded name; a group is relevant if any member shares a technology with `J`; its shared skills are the union; display name = lexicographically smallest original string. For roles: among best-ratio roles pick smallest casefolded, then smallest original string. Add both collisions to the P5 strategies.

**5. Fingerprint dedupe rule conflicts between requirements and design** — R10.5 vs design §4.1 `UNIQUE(dedupe_fingerprint)` and §11.4 step 2.
R10.5 skips only when the fingerprint matches "a job from another source" (implying same-source matches are inserted). The design skips matches from any source, and the global unique constraint forbids a same-source insert anyway.
Fix: R10.5 → "WHEN its dedupe fingerprint matches any existing job with a different (source, external_id) THE SYSTEM SHALL skip it as a duplicate." Add an integration test: same source, different `external_id`, same title/company/location → `duplicates=1`.

**6. Health endpoint body contradicts itself and the envelope rule** — R12.2, R12.6, design §8, §14.
R12.6: 200 `{"status":"ok","database":"ok"}`, 503 `database:"unavailable"`. §8 adds `version`. §14 says 503 `{status:"degraded", ...}`. R12.2 says every failure uses the error envelope.
Fix: R12.2 add "except `GET /api/health`, which always returns the health body". Pin one shape everywhere: 200 `{"status":"ok","database":"ok","version":"<app version>"}`; 503 `{"status":"degraded","database":"unavailable","version":"<app version>"}`.

**7. `POST /jobs/{id}/apply` status code undefined for an existing Saved/Interested application** — design §8, R2.10/R2.11.
The table says "201 (200 if already Applied)"; the Saved/Interested → Applied transition case is unspecified.
Fix: 201 only when a new application is created; 200 when an existing Saved/Interested application transitions to Applied and when it is already Applied. State this in R2.10/R2.11; cover all three plus the 409 case in `tests/api`.

**8. Resume skill extraction produces false positives** — design §9.1 (affects R8.3, R8.4, R8.5).
Case-insensitive whole-word matching of short canonicals/aliases (`go`, `rest`, `node`, `js`, `ts`, `py`, `ml`, `dl`, `r`) matches ordinary English ("go to market", "the rest of the team"). False matches inflate the compatibility score and hide real gaps, contradicting brief §1G "recommendations based on measurable differences".
Fix: define `AMBIGUOUS_RESUME_TERMS = {"go", "rest", "node", "js", "ts", "py", "ml", "dl", "r", "c"}` in `skill_catalog.py`; match these case-sensitively against the NFKC (not casefolded) text using canonical casings only (`Go`, `Golang`, `REST`, `Node`, `JS`, `TS`, `ML`, `DL`, `R`). Other terms keep the case-insensitive rule. Unit tests: "go to market" → no Go; "built REST APIs" → `rest apis`.

**9. Docker backend `DATABASE_URL` points at localhost** — design §18, `.env.example`.
`.env.example` sets `DATABASE_URL=...@localhost:5432/...`. Inside the backend container, localhost is the container, so `docker compose up` cannot reach `db` — breaking brief §16 and R11.4. §18 does not say how the backend gets a working URL.
Fix: §18 states compose sets on `backend`: `DATABASE_URL: postgresql+psycopg://${POSTGRES_USER:-internpilot}:${POSTGRES_PASSWORD:-change-me}@db:5432/${POSTGRES_DB:-internpilot}` (overrides `.env`). Comment in `.env.example` that the localhost URL is for host-run backends only.

**10. Timezone-aware columns load naive on SQLite** — design §4 (`DateTime(timezone=True)`), NFR2, §7 (`interview_date ≥ now`).
SQLite does not persist tz info; values load naive, and comparing with aware `clock.now()` raises `TypeError`. Dashboard, ordering and activity tests fail on the default test DB, contradicting NFR2 "without code changes".
Fix: add a `UTCDateTime` `TypeDecorator` in `app/models/base.py` for every timestamp column: on bind require aware and convert to UTC; on load attach `timezone.utc` if naive. Integration test round-trips an aware `interview_date` on SQLite and compares to `FixedClock.now()`.

**11. Response schemas referenced but not defined** — design §8.
`Profile`, `Application`, `JobState`, `Recommendation`, `ResumeAnalysis`, `Dashboard` have no field lists (e.g. type/order of `Profile.technical_skills`, shape of `Application.job`, whether `ResumeAnalysis` names the key `suggestions`). `types/api.ts` must mirror field names exactly, so this guarantees contract drift.
Fix: add §8.3 with exact fields:
- `Profile`: R1.1 fields; `technical_skills: list[str]` display names sorted by normalized name; `education`, `projects`, `certifications` per §4.1 shapes.
- `JobState`: `{job_id, is_bookmarked, is_hidden}`.
- `Application`: `{id, job_id, status, applied_at, deadline, interview_date, recruiter_name, recruiter_email, notes, outcome, created_at, updated_at, job: {id, title, company, location, deadline}}`.
- `Recommendation`: `{job: JobSummary, match_explanation: MatchExplanation}`.
- `Dashboard`: the §7 metric keys with their item shapes.
- `ResumeAnalysis`: §9.2 keys plus `suggestions: [{rule, message, evidence}]`.

### NIT

**12. Rounded JSON breaks R4.2 exact equality** — R4.2, §5.3. State R4.2 holds exactly on engine `Fraction` values; in JSON, `points` is within 0.01 of `weight × ratio`.

**13. Fixture fallback `source` value unstated** — §11.2. Specify: `FixtureSource` keeps `seed` for `seed_jobs.json` and uses `fixture` for `data/ingest/*.json` (affects updated vs duplicates counts on fallback).

**14. Location reason wording** — §5.4. Ratio-1 reason says "one of your preferred locations" even when the match comes from the home `location`. Use "matches your location or preferred locations".

**15. Error codes and class names inconsistent** — coding-standards.md vs design §6/§14. `EMAIL_TAKEN` and `CONFLICT` missing from the steering code list; §6 says `InvalidStatusTransition`, §14 `InvalidStatusTransitionError`. Add the codes; use `InvalidStatusTransitionError` everywhere.

**16. `GET /applications` unpaginated against steering** — coding-standards.md "lists that can grow are paginated". Document the exception (Kanban needs the full per-user set; service caps at 500).

**17. tasks.md ordering and legend** — 3.7 shows the score on JobCard before scoring is wired (4.4/4.9; 2.13 excludes score sort). Move the score display to 4.9. `[-]`/`[~]` markers have no legend; add one (`[ ]` todo, `[-]` in progress, `[~]` queued, `[x]` done).

**18. Required `DATABASE_URL` vs plain `pytest`** — §13.1. `tests/conftest.py` must set `DATABASE_URL` to `TEST_DATABASE_URL` or `sqlite+pysqlite://` (StaticPool) before importing the app; state it in §16.

**19. Interview prep edge cases** — §10. Job with no skills leaves `technical`/`skill` empty; add a generic 3-question technical fallback from `{title}`. LLM-appended questions continue `technical-{n}` numbering.

**20. Resume/skill input edge cases** — §8.1, §9. Treat whitespace-only resume text as empty for `RESUME_EMPTY`; strip trailing `.` from `missing_keywords` tokens; return 422 for `technical_skills` entries that normalize to `None` instead of silently dropping them.

**21. Untyped `RawBatch.items: list[dict]`** — §11.2 vs coding-standards (no `Any`). Define `JsonObject = dict[str, object]` and use `list[JsonObject]`.

**22. Compose `db` port exposure unspecified** — §18 vs security.md. Use `ports: ["127.0.0.1:5432:5432"]` and document it in README.

**23. R4.1 omits `job_id`** — R4.1 vs §5.5 JSON. Add `job_id` to R4.1's field list.

## Per-file summary

- **requirements.md** — EARS, numbered, testable; brief §4 example criteria present verbatim; P1–P6 derivable from R3.4–R3.10 and R5.2/5.4/5.5. Issues: 1, 5, 6, 7, 23.
- **design.md** — exact weights and point rules (Fraction, half-up, clamp), full reason table, defined `match_explanation`, complete data model with all brief §12 constraints, full brief §13 API surface. Issues: 1–4, 6–14, 16, 18–22.
- **tasks.md** — phases match brief §0 commit names; tasks cite R/§ IDs; PBT tasks use `test_p<n>_` names with requirement IDs. Issue: 17.
- **product.md** — purpose, target users, UX principles, terminology, constraints: all present.
- **architecture.md** — stack diagram, layering table, API boundaries, responsibilities, data flow, frontend rules, dependency rules: all present.
- **coding-standards.md** — general, Python, TypeScript, component structure, error handling, type safety, API conventions: all present. Issues: 15, 16.
- **testing.md** — layout, unit, integration/API, property (profile + naming + requirement citation), frontend, naming, coverage, determinism: all present.
- **security.md** — secrets/config, input validation, SQL injection, external API handling, credentials in git, secure errors, demo identity, CORS: all present.

## Verified assumptions

- Weights 35/10/15/15/10/5/5/5 sum to 100; only factors 1–2 read `S`, both non-decreasing in `S ∩ (R ∪ P)` and unaffected by skills outside it; projects use project technologies; `floor(total + 1/2)` is monotone → P2 follows from the rules.
- `P = normalize(preferred) − R` and frozenset `S` make P3/P4 derivable (given finding 2).
- Transition table covers all 8 statuses and `transition(x, x)` is a no-op → P6 derivable.
- All five steering docs exist with `inclusion: always` front matter (brief §5).
- `backend/pyproject.toml` matches steering: Ruff rules `E,F,I,B,UP,ANN,S,SIM,RUF`, line length 100, Black 100, pytest markers.
- `.env.example` matches design §13.1 variable for variable and contains placeholders only (`change-me`).
- `backend/tests/conftest.py` is empty; Hypothesis profile not yet registered, consistent with task 5.1 being queued.
- Brief §12 and §13 lists are fully covered by design §4.1 and §8.

## Unverified or wrong assumptions

- **Wrong:** NFR2 "runs on both without code changes" while using tz-aware columns on SQLite (finding 10).
- **Wrong:** Docker backend implicitly gets a working `DATABASE_URL` from `.env`; it would get a localhost URL (finding 9).
- **Wrong:** `DEMO_USER_EMAIL` treated as a stable identity although the email is editable (finding 1).
- **Unverified (needs network):** Remotive and Arbeitnow endpoints respond without cross-host redirects. Redirects are disabled, so a host change would force fallback every time; task 7.2 should record actual behavior.
