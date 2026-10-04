# Spec review — InternPilot AI (internship-intelligence), round 2

Intended location: `.agents/tasks/spec-review.md`. Writing there was blocked by a workspace permission rule (`deny fs_write matching ".agents/"`), so this copy lives in `docs/reviews/`.

Reviewed: `.kiro/specs/internship-intelligence/{requirements,design,tasks}.md` and `.kiro/steering/{product,architecture,coding-standards,testing,security}.md`, against the binding brief.

Note on the brief: reading `.agents/tasks/internpilot-master-brief.md` was also blocked (`deny fs_read matching ".agents/"`). I reviewed against `docs/project-brief.md`, which has the same title ("Master Build Brief") and the same numbered sections (0, 4, 5, 7, 12, 13).

## Verdict

**CHANGES_REQUESTED**: 0 HIGH, 5 MEDIUM, 7 NIT.

The specs are strong overall. Requirements are numbered EARS criteria and testable. All six Hypothesis properties trace to concrete criteria. The matching weights and point rules are exact, and `match_explanation` has a defined schema. The data model and API cover brief §12 and §13. All five steering docs cover their required sections and use `inclusion: always` front matter. The blocking findings are five gaps, each small and each fixable with a stated rule. Left as written, an implementer would have to guess on CORS, an error code, filter semantics, PATCH atomicity and activity-event triggers.

## Brief acceptance check

| Brief section | Result |
|---|---|
| §0 Phased commits / tasks drive work | tasks.md phases 1–8 map 1:1 to the brief's eight commits; every task cites R-IDs or § refs. ✓ |
| §4 EARS, numbered, testable, PBT-rich | R1–R15 with numbered `WHEN/IF/WHILE … THE SYSTEM SHALL` criteria. All four sample criteria from the brief appear verbatim (R3.1, R3.2, R2.10, R3.5). R3 is detailed enough to derive P1–P5 directly. ✓ |
| §4 design: architecture, data model, weights, API, properties | §3, §4, §5.3 (exact weights 35/10/15/15/10/5/5/5 = 100 and exact `Fraction` ratio rules), §8, §17. ✓ |
| §5 Steering contents | product (purpose, users, UX, terminology, constraints), architecture (stack, layering, API boundaries, responsibilities, data flow, dependency rules), coding-standards (TS, Python, naming, errors, type safety, components, API conventions), testing (unit/integration/PBT, naming, coverage, determinism), security (secrets, env, validation, SQLi, external APIs, git credentials, error responses). All have `inclusion: always`. ✓ |
| §7 Six properties | P1–P6 in requirements and §17, each mapped to criteria and given a test name. P2 is provable from §5.3: only factors 1–2 read `S`, and both are non-decreasing in `S ∩ (R ∪ P)`. The half-up rounding is monotone. ✓ |
| §12 Data model | `users.email` unique; `skills.normalized_name` unique; `user_skills` composite PK; `UNIQUE(source, external_id)` plus a unique sha256 `dedupe_fingerprint`; `job_skills.is_required`; `applications` `UNIQUE(user_id, job_id)` and `ck_applications_status`. Per-user state lives in `user_job_states`. ✓ |
| §13 API | Every listed endpoint is in §8, plus bookmark/hide (PUT/DELETE), `/jobs/{id}/apply`, `/applications/meta` and `/health`. ✓ |

## Findings

### requirements.md

**F1 (MEDIUM): job-list `skills` and `location` filter semantics are undefined.** R2.4 lists "location substring, source, skills" filters, and §8 lists `skills (comma list)` and `location`. Neither says how they compare:
- Is `skills` checked against required skills only, or required ∪ preferred?
- Are the filter values normalized?
- What happens with an entry that normalizes to `None`?
- Is the location match case-sensitive?

API tests cannot be written without guessing. **Fix** (add to R2.4 and §8.1):
> `skills`: comma-separated, ≤ 10 entries, each passed through `normalize_skill`. An entry normalizing to `None` → 422. A job matches if any normalized entry ∈ its required ∪ preferred skills. `location`: 1–100 chars; a job matches if `casefold(location)` is a substring of `casefold(job.location)`. The match is done in SQL with `ilike` and `%`/`_` escaped. `source`: single enum value from `seed|fixture|remotive|arbeitnow|payload`.

**F2 (MEDIUM): PATCH atomicity with an invalid transition is unspecified.** R5.5 says the stored status stays unchanged on a disallowed transition. It does not say whether other fields in the same `ApplicationUpdate` (notes, dates) still get saved. A partial save would make the 409 misleading. It would also break P6's stateful "row unchanged" check. **Fix** (append to R5.5):
> …and SHALL NOT persist any other field from the same request (the whole PATCH is rejected).

In §6, run `transition()` before applying any field changes in `ApplicationService.update`.

**F3 (NIT): R12.2's status list omits 401.** R13.3 defines 401 `UNKNOWN_DEMO_USER`, but R12.2's enumeration skips it. **Fix:** add "401 unknown demo user" to the R12.2 list.

### design.md

**F4 (MEDIUM): §11.5 names the wrong exception for the 502.** §11.5 says "With `fallback=false`, raise `UpstreamUnavailableError` → 502". In the already-implemented `backend/app/core/errors.py`, `UpstreamUnavailableError.default_code` is `"UPSTREAM_UNAVAILABLE"`. Raising it would return `UPSTREAM_UNAVAILABLE`, but R10.7 and coding-standards require `INGESTION_SOURCE_UNAVAILABLE`, which is the subclass `IngestionSourceUnavailableError`. **Fix:** change §11.5 to "raise `IngestionSourceUnavailableError` (502 `INGESTION_SOURCE_UNAVAILABLE`)". Add an API test asserting that code.

**F5 (MEDIUM): CORS is not designed, but the Docker demo needs it.** The frontend runs at `localhost:5173` (nginx) and reaches the backend at `localhost:8000` through `VITE_API_BASE_URL`. Those are different origins, so every browser call will fail without CORS. `CORS_ORIGINS` is in §13.1 and the security steering says "CORS allows only `CORS_ORIGINS`". Yet §3.2 `create_app` and §18 never install `CORSMiddleware`, and the current `backend/app/main.py` doesn't install it either. The default value of the `VITE_API_BASE_URL` build arg is also unstated. **Fix** (add to §3.2/§14 and a task under 2.3):
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,   # never "*"
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "X-Demo-User", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)
```
Also state that the §18 `VITE_API_BASE_URL` build-arg default is `http://localhost:8000/api`. Add an API test: a preflight from an allowed origin gets 200 with `access-control-allow-origin`, and one from a disallowed origin gets no ACAO header.

**F6 (MEDIUM): activity-event triggers are incomplete.** §4.1 defines the types `job_bookmarked`, `job_hidden`, `application_updated` and `jobs_ingested`, but never says exactly when each is written. That matters because `recent_activity` (R6.1) is a user-visible metric that tests assert on. The open questions:
- Does un-bookmarking write an event? Does a repeated, idempotent PUT?
- Does a PATCH that changes status and notes write one event or two?
- Which `user_id` does `jobs_ingested` get when ingestion runs from `python -m app.cli seed|ingest`, where there is no request user?

**Fix** (add a table to §4.1):
> `job_bookmarked` / `job_hidden`: only when the flag changes false→true; no event on unset or no-op. `status_changed`: when the status actually changes. `application_updated`: when a PATCH changes non-status fields without a status change (a PATCH with both writes only `status_changed`). `application_created` / `application_deleted`: always. `profile_updated`: every successful PUT. `jobs_ingested`: one per run, attributed to the request user; for CLI runs, attributed to the `seed_key='demo'` user. If that user does not exist yet, no event is written.

**F7 (NIT): the `ALIASES` invariant contradicts its own entry.** §5.1 says "every alias value is … not an alias key", but the list includes `ci/cd → ci/cd`. That makes `ci/cd` both a key and a value, so the specified unit test could fail. **Fix:** drop the identity key and keep `cicd → ci/cd`.

**F8 (NIT): NFKC-then-casefold is not guaranteed idempotent for all Unicode.** `casefold()` can emit sequences that NFKC changes again. The Hypothesis idempotence check runs on arbitrary text and could find such a case. **Fix:** in §5.1 step 1, use `unicodedata.normalize("NFKC", unicodedata.normalize("NFKC", raw).casefold())`. This is the NFKC_Casefold-style closure.

**F9 (NIT): the ambiguous resume term `R` will produce false positives.** With the §9.1 boundary regex, `R → {R}` matches "R&D" and initials such as "John R. Smith". **Fix:** for `r` and `c`, also require that the next character is not `&` and not `.` followed by a space. Add unit tests for `"R&D"` → nothing and `"John R. Smith"` → nothing.

**F10 (NIT): the error-code list and the code are out of sync.** §14 and `errors.py` emit `NOT_READY`, `UPSTREAM_UNAVAILABLE`, `METHOD_NOT_ALLOWED`, `BAD_REQUEST`, `UNSUPPORTED_MEDIA_TYPE` and `HTTP_ERROR`. coding-standards.md's code list doesn't include them. **Fix:** add them to the coding-standards list as "framework/base codes".

**F11 (NIT): search escaping is not stated in the design.** The security steering requires escaping `%`/`_` for `q`, but §3.3 and §8 don't mention it. **Fix:** in §3.3, add "`q` and `location` use `ilike` with `escape='\\'` after escaping `\`, `%`, `_`". Add a unit test: `q="100%"` matches only literal `100%`.

**F12 (NIT): "update mutable fields" (§11.4 rule 1) is not enumerated.** **Fix:** list them. Mutable: title, company, location, employment_type, work_mode, experience_level, min_education_level, description, salary_*, application_url, deadline, skills, dedupe_fingerprint. Immutable: `source`, `external_id`, `discovered_at`.

### tasks.md

No separate findings. Once F5 is accepted, add a CORS sub-task to 2.3 (or a new 2.3a). Fixes for F1, F2, F4 and F6 fall under existing tasks 2.12–2.14 and 2.18.

### Steering docs

No blocking findings. All five cover every section the brief requires. F10 is a sync fix in coding-standards.md.

## Verified assumptions

- `backend/app/core/errors.py` defines the §14 hierarchy: `AppError`, `NotFoundError`, `ConflictError` with `DuplicateApplicationError`/`InvalidStatusTransitionError`/`EmailTakenError`, `ResumeEmptyError`, `PayloadTooLargeError`, `IngestionSourceUnavailableError`, `UnknownDemoUserError`, `DemoUserNotSeededError` and `DatabaseUnavailableError`. It strips `input`/`ctx` from validation errors and returns a generic 500.
- `backend/app/core/config.py` has every §13.1 variable with the stated defaults. `DATABASE_URL` is required and fails fast. `LLM_API_KEY` is a `SecretStr`. CORS origins reject wildcards.
- `backend/app/core/middleware.py` validates request ids against `^[A-Za-z0-9-]{1,64}$` and caps bodies at 5 MB, checking both Content-Length and the streamed byte count, with the 413 envelope.
- `backend/app/main.py` wraps the stack in `RequestIdMiddleware` outermost, so 500 responses also carry `X-Request-ID`.
- `.env.example` lists every §13.1 variable plus `POSTGRES_*` and `VITE_API_BASE_URL`.
- All five steering files exist with `inclusion: always` front matter.
- P2 holds by construction under §5.2–§5.3. Only factors 1–2 read `S`, `P` excludes `R`, and `floor(total + 1/2)` is monotone.

## Unverified or wrong assumptions

- Wrong: §11.5 implies `UpstreamUnavailableError` yields `INGESTION_SOURCE_UNAVAILABLE`. In the code it yields `UPSTREAM_UNAVAILABLE` (F4).
- Wrong: the design assumes the browser can call the backend cross-origin. No CORS middleware is designed or installed (F5).
- Wrong: §5.1 says alias values are never alias keys. `ci/cd` contradicts it (F7).
- Unverified: the `.agents/tasks/internpilot-master-brief.md` copy itself. Access was denied, so `docs/project-brief.md` was used.
- Unverified: NFR1 timings (< 500 ms for 1,000 jobs, < 1 ms per match). These are plausible but can only be checked once the engine exists.
- Unverified: `mcp-server-fetch` availability through `uvx` on this machine. That belongs to Phase 7 and was not checked in this documentation review.
