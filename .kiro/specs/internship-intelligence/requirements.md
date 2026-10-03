# Requirements: Internship Intelligence (InternPilot AI)

## Introduction

InternPilot AI is an internship and early-career command center for students and fresh graduates. It discovers opportunities, computes a transparent, deterministic 0–100 match score for every job with a machine-readable `match_explanation`, tracks applications in a table and a Kanban board, analyzes a resume against a selected job, and generates interview preparation material. Every core feature works offline on seeded data; no external LLM or network service is required.

This document is the source of truth for behavior. `design.md` defines how each requirement is met and `tasks.md` sequences the work. Requirement IDs (`R<n>`) and acceptance-criterion IDs (`R<n>.<m>`) are referenced by tasks and tests.

### Conventions

- Criteria use EARS form: `WHEN <trigger> THE SYSTEM SHALL <response>`, `IF <condition> THEN THE SYSTEM SHALL <response>`, `WHILE <state> THE SYSTEM SHALL <response>`, or `THE SYSTEM SHALL <response>` for ubiquitous rules.
- "The user" means the current demo user resolved per R13.
- "Normalized skill" means a skill name after the normalization rules in R3.2 (`design.md` §5.1).
- "Valid status" means exactly one of: `Saved`, `Interested`, `Applied`, `Assessment`, `Interview`, `Rejected`, `Offer`, `Withdrawn`.
- "Match threshold" is 60: a job "matches the profile" when its score is ≥ 60.
- Dates are ISO-8601. Timestamps are stored and returned in UTC.

### Glossary

| Term | Meaning |
|---|---|
| Profile | The user's career data (R1). |
| Job | A discovered opportunity (R2). |
| Match | The result of the matching engine for one (profile, job) pair: score + `match_explanation`. |
| Factor | One weighted component of the score (required skills, preferred skills, role, experience, location, work mode, education, projects). |
| Application | A tracker record linking the user to one job with exactly one status (R5). |
| Job state | Per-user flags on a job: bookmarked, hidden. |
| Ingestion | Importing jobs from a source (public API, fixture, or captured payload) with normalization, validation and dedupe (R10). |

---

## Requirement 1: User profile management

**User Story:** As a student, I want to maintain a complete career profile, so that matching, resume analysis and interview prep reflect who I am.

#### Acceptance Criteria

1. WHEN the user requests their profile THE SYSTEM SHALL return name, email, location, target roles, preferred locations, preferred work modes, experience level, education level, education entries, technical skills, soft skills, projects, certifications, resume text, GitHub URL, portfolio URL, LinkedIn URL, created_at and updated_at.
2. WHEN the user submits a valid profile update THE SYSTEM SHALL persist every submitted field in PostgreSQL, update `updated_at`, and return the stored profile.
3. WHEN the user submits technical skills THE SYSTEM SHALL store each skill once per normalized name (case-, whitespace- and alias-insensitive) and link it to the shared skill catalog.
4. IF a profile update violates a validation rule (required name/email, email format, enum values, list sizes, string lengths, URL scheme/host rules in `design.md` §8.1) THEN THE SYSTEM SHALL reject the whole update with HTTP 422 and the error envelope, and SHALL NOT persist any part of it.
5. IF a profile URL field is present and does not use `http` or `https` THEN THE SYSTEM SHALL reject it; IF `github_url` is not on `github.com` or `linkedin_url` is not on `linkedin.com` (optionally `www.`) THEN THE SYSTEM SHALL reject it.
6. WHEN the user's profile changes THE SYSTEM SHALL use the new profile for every subsequent match, recommendation, dashboard, resume-analysis and interview-prep response (no stale cached scores).
7. WHEN the profile is updated THE SYSTEM SHALL record a `profile_updated` activity event.

## Requirement 2: Job discovery

**User Story:** As a student, I want to search, filter, sort and page through opportunities and act on them, so that I can focus on the roles worth my time.

#### Acceptance Criteria

1. THE SYSTEM SHALL store for each job: title, company, location, employment type (`internship`, `full_time`, `part_time`, `contract`), work mode (`remote`, `hybrid`, `onsite`), required skills, preferred skills, experience level, minimum education level (optional), salary/stipend min/max/currency/period (optional), application URL, deadline (optional), source, external ID, description and discovered_at.
2. WHEN the user lists jobs THE SYSTEM SHALL return a page of job summaries, each with its match score, bookmark flag, hidden flag and the user's application status (or null), plus `total`, `page`, `page_size` and `total_pages`.
3. WHEN the user supplies a search query `q` THE SYSTEM SHALL return only jobs whose title, company or description contains the query case-insensitively.
4. WHEN the user supplies filters (employment type, work mode, experience level, location substring, source, skills, minimum score, bookmarked only) THE SYSTEM SHALL return only jobs satisfying all supplied filters; multi-valued filters match any of their values.
5. WHEN the user selects a sort key (`match_score`, `discovered_at`, `deadline`, `title`, `company`, `salary`) and order THE SYSTEM SHALL order results accordingly, breaking ties by job id ascending, with null deadlines/salaries sorted last regardless of order. The default sort SHALL be `match_score` descending.
6. WHEN the user requests a page beyond the last page THE SYSTEM SHALL return an empty `items` list with correct `total` and `total_pages` (not an error).
7. WHILE a job is hidden by the user THE SYSTEM SHALL exclude it from job lists (unless `include_hidden=true`), recommendations, the "matching jobs" metric and top recommendations, but SHALL still return it by id.
8. WHEN the user bookmarks or un-bookmarks a job THE SYSTEM SHALL set the bookmark flag idempotently and return the updated job state.
9. WHEN the user hides or un-hides a job THE SYSTEM SHALL set the hidden flag idempotently and return the updated job state.
10. WHEN a user applies to a job ("mark as applied") THE SYSTEM SHALL create an application record with status "Applied" and `applied_at` set to today, or, if an application in `Saved` or `Interested` already exists, transition it to `Applied`.
11. IF the user marks a job as applied while its application is already in a status other than `Saved`, `Interested` or `Applied` THEN THE SYSTEM SHALL return HTTP 409 `INVALID_STATUS_TRANSITION` and leave the application unchanged; IF it is already `Applied` THEN THE SYSTEM SHALL return the existing application unchanged.
12. IF a job id does not exist THEN THE SYSTEM SHALL return HTTP 404 `NOT_FOUND` for every job-scoped endpoint.
13. IF list parameters are invalid (page < 1, page_size outside 1–100, unknown enum or sort key, `q` longer than 100 characters, `min_score` outside 0–100) THEN THE SYSTEM SHALL return HTTP 422 `VALIDATION_ERROR`.
14. THE SYSTEM SHALL NOT scrape LinkedIn or any website that prohibits automated access; jobs come only from public no-auth APIs, local fixtures or user-supplied payloads (R10).

## Requirement 3: Deterministic match scoring

**User Story:** As a student, I want a transparent 0–100 compatibility score for every job, so that I can trust and compare recommendations.

#### Acceptance Criteria

1. WHEN a user views a job THE SYSTEM SHALL calculate a compatibility score between 0 and 100 (integer, inclusive) for the user's current profile.
2. WHEN a job contains required skills THE SYSTEM SHALL compare them against the user's normalized skill set, where normalization lowercases, trims, collapses internal whitespace and maps known aliases to a canonical name (e.g. `ReactJS` → `react`, `Postgres` → `postgresql`).
3. THE SYSTEM SHALL compute the score as the rounded (half-up) sum of eight factor scores with fixed weights — required skills 35, preferred skills 10, role similarity 15, experience 15, location 10, work mode 5, education 5, project relevance 5 — using exactly the point rules in `design.md` §5.
4. THE SYSTEM SHALL ensure every factor's points lie within `[0, weight]` and the score lies within `[0, 100]` for every valid profile and job, including empty skill lists, empty target roles, unknown experience/education, and jobs with no listed skills.
5. WHEN the user adds a matching skill THE SYSTEM SHALL NOT decrease the resulting job match score. (A matching skill is one whose normalized form is in the job's required or preferred skills.)
6. WHEN the user adds a skill whose normalized form is in neither the job's required nor preferred skills THE SYSTEM SHALL leave that job's score and explanation unchanged.
7. WHEN the user's skill list contains duplicates — identical entries, case variants, whitespace variants or aliases of the same canonical skill — THE SYSTEM SHALL produce the same score and explanation as for the de-duplicated list.
8. IF a job's required skill is absent from the user's normalized skill set THEN THE SYSTEM SHALL give that skill no credit: it SHALL appear in `missing_required_skills`, SHALL NOT appear in `matched_required_skills`, and the required-skills factor SHALL equal `35 × |matched required| / |required|`.
9. IF the user's normalized skills share no element with a job's required skills (and the job lists at least one) THEN THE SYSTEM SHALL award 0 points for the required-skills factor; the same holds for preferred skills.
10. WHEN the system computes match(profile, job) more than once for equal inputs THE SYSTEM SHALL return identical scores and identical explanations, independent of the order of skills, target roles, preferred locations or projects in the input and independent of time, randomness, locale or network.
11. THE SYSTEM SHALL compute matches without calling any external LLM or network service.
12. WHEN the score is computed THE SYSTEM SHALL use the same engine for job lists, job detail, `POST /api/jobs/{id}/match`, recommendations, dashboard metrics and resume analysis, so the same (profile, job) pair never shows two different scores.

## Requirement 4: Match explanation

**User Story:** As a student, I want to see exactly why a role matches or not, so that I know what to improve.

#### Acceptance Criteria

1. WHEN a match is computed THE SYSTEM SHALL return a `match_explanation` object containing: `score`, `algorithm_version`, an ordered list of eight `factors` (key, label, weight, points, ratio, detail), `matched_required_skills`, `missing_required_skills`, `matched_preferred_skills`, `missing_preferred_skills`, `positive_reasons` and `negative_reasons`.
2. THE SYSTEM SHALL make `score` equal the half-up rounding of the sum of factor points, and each factor's `points` equal `weight × ratio`.
3. WHEN a required skill is matched THE SYSTEM SHALL add a positive reason of the form `"<Skill> matches required skill"`; WHEN it is missing THE SYSTEM SHALL add a negative reason of the form `"<Skill> experience is missing (required)"`.
4. WHEN preferred skills are matched or missing THE SYSTEM SHALL add `"<Skill> matches preferred skill"` positive reasons and `"<Skill> is a preferred skill not in your profile"` negative reasons respectively.
5. THE SYSTEM SHALL add exactly one reason for each of role similarity, experience, location, work mode, education and project relevance, with the polarity and template defined for that factor's case in `design.md` §5.4.
6. THE SYSTEM SHALL order skill lists alphabetically by normalized name and order reasons by factor order, then alphabetically within a factor.
7. WHEN the UI displays a match THE SYSTEM SHALL show `MATCH SCORE: <score>/100`, positive reasons prefixed with `+` and negative reasons prefixed with `-`, and the per-factor breakdown.

## Requirement 5: Application tracking

**User Story:** As a student, I want to track every application through its lifecycle in a table and a Kanban board, so that nothing falls through the cracks.

#### Acceptance Criteria

1. WHEN the user creates an application for a job THE SYSTEM SHALL create one record with the given status (default `Saved`) and optional notes, application date, deadline, interview date, recruiter name, recruiter email and outcome.
2. THE SYSTEM SHALL ensure every application always has exactly one valid status, enforced by the API schema, the service state machine and a database check constraint.
3. IF the user creates an application for a job that already has one THEN THE SYSTEM SHALL return HTTP 409 `DUPLICATE_APPLICATION` (unique per user and job).
4. WHEN the user changes an application's status THE SYSTEM SHALL apply it only if the transition is allowed by the transition table in `design.md` §6; an update to the current status SHALL be a no-op success.
5. IF a requested status transition is not allowed, or the status value is not a valid status THEN THE SYSTEM SHALL return HTTP 409 `INVALID_STATUS_TRANSITION` (or 422 for unknown values) and SHALL leave the stored status unchanged.
6. WHEN an application is created in or moves to a submitted status (`Applied`, `Assessment`, `Interview`, `Offer`, `Rejected`) and `applied_at` is empty THE SYSTEM SHALL set `applied_at` to today.
7. WHEN the user edits notes, interview date, recruiter contact, application date, deadline or outcome THE SYSTEM SHALL persist the change and update `updated_at`.
8. WHEN the user deletes an application THE SYSTEM SHALL remove it and return HTTP 204; IF it does not exist or belongs to another user THEN THE SYSTEM SHALL return HTTP 404.
9. WHEN the user lists applications THE SYSTEM SHALL return each with its job summary (title, company, location, deadline) and support filtering by status.
10. THE SYSTEM SHALL expose the list of statuses and allowed transitions through the API so the UI renders only allowed moves without duplicating business rules.
11. WHEN the user views applications THE SYSTEM SHALL offer a table view and a Kanban board with one column per status; moves SHALL be possible by drag-and-drop and by keyboard-accessible "Move to" controls.
12. WHEN an application is created, changes status, or is deleted THE SYSTEM SHALL record an activity event.

## Requirement 6: Career dashboard

**User Story:** As a student, I want a dashboard summarizing my search, so that I can see progress and what needs attention.

#### Acceptance Criteria

1. WHEN the user opens the dashboard THE SYSTEM SHALL return: total jobs discovered, jobs matching the profile, applications submitted, interviews scheduled, offers received, response rate, upcoming deadlines, recent activity, top recommended opportunities, a status breakdown, applications over time and a score distribution.
2. THE SYSTEM SHALL compute each metric exactly as defined in `design.md` §7 (e.g. response rate = responded ÷ submitted × 100 rounded to one decimal, 0.0 when nothing is submitted).
3. WHEN application data changes THE SYSTEM SHALL reflect it in the next dashboard response (no stale aggregates).
4. THE SYSTEM SHALL include every one of the eight statuses in the status breakdown, with zero counts where applicable.
5. WHEN there is no data THE SYSTEM SHALL return zeros and empty lists rather than errors, and the UI SHALL show empty states.

## Requirement 7: Recommendations

**User Story:** As a student, I want the best-fit opportunities surfaced automatically.

#### Acceptance Criteria

1. WHEN the user requests recommendations THE SYSTEM SHALL return up to `limit` (default 5, 1–20) jobs ordered by score descending, then deadline ascending (nulls last), then id ascending, each with its `match_explanation`.
2. THE SYSTEM SHALL exclude hidden jobs and jobs whose application status is anything other than `Saved` or `Interested`.
3. IF `limit` is outside 1–20 THEN THE SYSTEM SHALL return HTTP 422.

## Requirement 8: Resume / skill analysis

**User Story:** As a student, I want to compare my resume to a specific job, so that I get concrete, measurable improvements.

#### Acceptance Criteria

1. WHEN the user requests an analysis for a job THE SYSTEM SHALL analyze the supplied `resume_text`, or the profile's resume text when none is supplied.
2. THE SYSTEM SHALL return matching skills, missing skills (each flagged required or preferred), relevant projects with the job skills they demonstrate, missing keywords, suggested improvements, a compatibility score and its `match_explanation`.
3. THE SYSTEM SHALL extract resume skills by detecting known catalog skills and aliases as whole words/phrases in the resume text, case-insensitively.
4. THE SYSTEM SHALL compute the compatibility score with the R3 engine using the profile with its technical skills replaced by the skills extracted from the resume.
5. THE SYSTEM SHALL generate each suggestion from a measurable difference (rules in `design.md` §9.3) and attach the evidence (skill, keyword, count or project) that triggered it.
6. THE SYSTEM SHALL NOT return a rewritten resume or modify the stored resume text.
7. IF both the supplied and the profile resume text are empty THEN THE SYSTEM SHALL return HTTP 422 `RESUME_EMPTY`; IF resume text exceeds 50,000 characters THEN THE SYSTEM SHALL return HTTP 422.
8. WHEN the same resume text and job are analyzed twice THE SYSTEM SHALL return identical results.

## Requirement 9: Interview preparation

**User Story:** As a student, I want a tailored interview prep sheet for a selected job.

#### Acceptance Criteria

1. WHEN the user requests interview prep for a job THE SYSTEM SHALL return role-specific, technical, HR, project and required-skill question sections and a list of suggested preparation topics.
2. THE SYSTEM SHALL generate questions from deterministic templates using the job's title, company, required/preferred skills and the user's projects, with the per-section limits in `design.md` §10.
3. THE SYSTEM SHALL rank preparation topics: missing required skills `high`, matched required skills `medium`, missing preferred skills `low`.
4. THE SYSTEM SHALL generate questions through a provider interface so that an LLM provider can be plugged in without changing callers.
5. IF an optional LLM provider is enabled and fails or times out THEN THE SYSTEM SHALL return the template result, mark `provider` as `template`, and log a warning.
6. WHEN the same job and profile are requested twice with the template provider THE SYSTEM SHALL return identical output.

## Requirement 10: Job ingestion with fallback

**User Story:** As a student, I want to pull fresh jobs from public sources, so that my list stays current, without the app breaking when those sources are down.

#### Acceptance Criteria

1. WHEN ingestion is requested for a public source (`remotive` or `arbeitnow`) THE SYSTEM SHALL fetch only from hosts in `INGEST_ALLOWED_HOSTS`, over HTTPS, with the configured timeout and a 5 MB response-size limit.
2. WHEN ingestion is requested with source `payload` THE SYSTEM SHALL accept a JSON payload (e.g. captured with the MCP fetch tool) in `remotive`, `arbeitnow` or `normalized` format, up to 500 items.
3. WHEN ingestion is requested with source `fixture` THE SYSTEM SHALL load jobs only from `data/seed_jobs.json` and `data/ingest/*.json` (no caller-supplied file paths).
4. WHEN raw items are ingested THE SYSTEM SHALL normalize them (HTML stripped, whitespace collapsed, enums mapped, skills normalized) and validate each with Pydantic; invalid items SHALL be counted as rejected with a reason and SHALL NOT abort the batch.
5. WHEN an item's (source, external_id) already exists THE SYSTEM SHALL update the existing job; WHEN its dedupe fingerprint (normalized title + company + location) matches a job from another source THE SYSTEM SHALL skip it as a duplicate; otherwise THE SYSTEM SHALL insert it.
6. IF a public source fails (network error, timeout, non-2xx, oversized, invalid JSON, disallowed host) and `fallback` is true (default) THEN THE SYSTEM SHALL ingest from the fixture source, set `fallback_used=true` and include the failure reason in `errors`.
7. IF a public source fails and `fallback` is false THEN THE SYSTEM SHALL return HTTP 502 `INGESTION_SOURCE_UNAVAILABLE` without partial writes.
8. WHEN ingestion completes THE SYSTEM SHALL return counts `fetched`, `created`, `updated`, `duplicates`, `rejected`, the effective source, `fallback_used` and up to 50 errors.
9. THE SYSTEM SHALL start and serve all features without network access, without MCP, and without running ingestion.

## Requirement 11: Seed and demo data

**User Story:** As a demo presenter, I want a meaningful dataset on first start.

#### Acceptance Criteria

1. WHEN the seed command runs THE SYSTEM SHALL load 1 demo user, at least 20 skills, at least 30 jobs (varied companies, locations, skills, experience levels, work modes, internship and full-time) and at least 10 applications across at least 6 statuses.
2. WHEN the seed command runs again THE SYSTEM SHALL NOT create duplicates (idempotent) and SHALL NOT overwrite user-edited profile data or application changes.
3. THE SYSTEM SHALL express seeded deadlines and dates relative to the seed date so upcoming deadlines are meaningful whenever the demo is started.
4. WHEN `docker compose up` runs THE SYSTEM SHALL apply migrations and the idempotent seed before serving the API.

## Requirement 12: API contract and error handling

**User Story:** As a frontend developer, I want a consistent, documented REST API.

#### Acceptance Criteria

1. THE SYSTEM SHALL expose the REST endpoints listed in `design.md` §8 under `/api`, documented through FastAPI's OpenAPI schema.
2. IF any request fails THEN THE SYSTEM SHALL respond with `{"error": {"code", "message", "details"}}` and the matching HTTP status (422 validation, 404 not found, 409 conflict, 413 payload too large, 502 upstream unavailable, 503 not ready, 500 internal).
3. IF an unexpected exception occurs THEN THE SYSTEM SHALL return HTTP 500 `INTERNAL_ERROR` with a generic message, without stack traces, SQL or secrets, and log the exception with the request id.
4. THE SYSTEM SHALL validate every request body, path and query parameter with typed Pydantic schemas and reject unknown body fields.
5. THE SYSTEM SHALL return an `X-Request-ID` header on every response.
6. WHEN `GET /api/health` is called THE SYSTEM SHALL return HTTP 200 with `{"status":"ok","database":"ok"}` when the database is reachable, else HTTP 503 with `database: "unavailable"`.

## Requirement 13: Demo identity and configuration

**User Story:** As an operator, I want environment-based configuration and a simple demo identity.

#### Acceptance Criteria

1. THE SYSTEM SHALL read all configuration (database URL, CORS origins, demo user, ingestion settings, LLM settings, log level) from environment variables with documented defaults in `.env.example`, and SHALL NOT contain hard-coded secrets.
2. WHEN a request has no `X-Demo-User` header THE SYSTEM SHALL act as the user whose email equals `DEMO_USER_EMAIL`; WHEN the header carries an existing user's email THE SYSTEM SHALL act as that user.
3. IF `X-Demo-User` names an unknown user THEN THE SYSTEM SHALL return HTTP 401 `UNKNOWN_DEMO_USER`; IF the default demo user is not seeded THEN THE SYSTEM SHALL return HTTP 503 `DEMO_USER_NOT_SEEDED`.
4. THE SYSTEM SHALL scope applications, job states and activity to the resolved user.
5. THE SYSTEM SHALL document that the demo identity is not production authentication.

## Requirement 14: Frontend experience

**User Story:** As a student, I want a polished, accessible interface.

#### Acceptance Criteria

1. THE SYSTEM SHALL provide routes for Dashboard, Jobs, Job detail, Applications (table and board), Resume analysis, Interview prep and Profile, reachable from a persistent sidebar (collapsible on narrow screens).
2. WHILE data is loading, empty or failed THE SYSTEM SHALL show a loading skeleton, an empty state, or an error state with a retry action respectively.
3. WHEN a mutation succeeds or fails THE SYSTEM SHALL show a toast describing the outcome.
4. THE SYSTEM SHALL label every form control, keep visible focus styles, make all interactions keyboard-operable (including Kanban moves), and meet WCAG AA color contrast for text in the design tokens.
5. THE SYSTEM SHALL render the match score as a ring/gauge with the numeric `<score>/100` as text (not color alone).
6. THE SYSTEM SHALL keep business logic out of React components: data access lives in the API client and hooks; scoring, transitions and metrics come from the backend.
7. THE SYSTEM SHALL render dashboard charts (status breakdown, applications over time, score distribution) with Recharts.

## Requirement 15: Optional LLM provider

**User Story:** As an operator, I want to optionally enrich interview prep with an LLM without making it a dependency.

#### Acceptance Criteria

1. WHILE `LLM_ENABLED` is false or `LLM_API_KEY`/`LLM_BASE_URL`/`LLM_MODEL` is unset THE SYSTEM SHALL use only deterministic providers and make no LLM calls.
2. WHEN the LLM provider is enabled and configured THE SYSTEM SHALL use it only for interview-prep question enrichment, never for match scores, explanations, dashboard metrics or resume compatibility scores.
3. IF the LLM call fails, times out (15 s) or returns an unparseable response THEN THE SYSTEM SHALL fall back per R9.5.

---

## Non-functional requirements

- **NFR1 Performance:** With 1,000 jobs, `GET /api/jobs` (any sort) and `GET /api/dashboard` SHALL respond in under 500 ms on a developer laptop; a single match computation SHALL take under 1 ms.
- **NFR2 Portability:** SQLAlchemy models SHALL run on PostgreSQL (production/demo) and SQLite (default test database) without code changes.
- **NFR3 Reproducibility:** Tests SHALL be deterministic (fixed Hypothesis settings profile, frozen "today" where dates matter, no network).
- **NFR4 Security:** Follow `.kiro/steering/security.md`: no secrets in git, parameterized queries only (SQLAlchemy), input validation everywhere, allow-listed outbound hosts, generic error responses.
- **NFR5 Accessibility:** Per R14.4. Full WCAG validation requires manual testing with assistive technologies.
- **NFR6 Maintainability:** Layering per `.kiro/steering/architecture.md`; backend coverage ≥ 80% lines overall and ≥ 95% for `app/services/matching`.

## Correctness properties (for property-based testing)

These are derived from the criteria above and are implemented with Hypothesis in `backend/tests/property/`.

| ID | Property | Criteria |
|---|---|---|
| P1 | Score bounds: for all valid profiles and jobs, `0 ≤ score ≤ 100`, score is an int, and every factor has `0 ≤ points ≤ weight`. | R3.1, R3.3, R3.4, R4.2 |
| P2 | Matching-skill monotonicity: adding a skill in the job's required ∪ preferred set never lowers the score; adding an unrelated skill changes nothing. | R3.5, R3.6 |
| P3 | Duplicate no-impact: duplicating skills (identical, case/whitespace variants, aliases) yields the identical result. | R3.2, R3.7 |
| P4 | Missing required skills get no credit. | R3.8, R3.9 |
| P5 | Determinism and order-independence of match(p, j), including the explanation. | R3.10, R3.11 |
| P6 | Status validity: under any sequence of transition attempts, an application has exactly one valid status; invalid attempts leave it unchanged. | R5.2, R5.4, R5.5 |

## Assumptions

- A1: Single demo user is sufficient; multi-user auth is out of scope (R13).
- A2: The match threshold for "matching jobs" is 60.
- A3: Bookmarking is a job-state flag and does not create an application; the tracker's `Saved` status is separate.
- A4: Jobs are global (shared across users); bookmark/hidden flags and applications are per user.
- A5: Project relevance is the only optional factor; when a job lists no skills it receives neutral credit as defined in `design.md` §5.

## Out of scope

- Scraping LinkedIn or any site that prohibits automated access.
- Production authentication, multi-tenant accounts, password management.
- Automatically rewriting the user's resume.
- Using an LLM for scoring or any core feature.
- Email/calendar integrations, notifications, file uploads (resume is pasted text).
- Deploying to a hosted environment.
