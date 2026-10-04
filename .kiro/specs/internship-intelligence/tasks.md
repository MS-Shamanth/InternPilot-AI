# Implementation Plan: Internship Intelligence (InternPilot AI)

Work proceeds phase by phase; each phase ends with a commit named in the brief. Tick a box (`- [x]`) only when the code exists, follows `.kiro/steering/`, and its tests pass. References: `R<n>.<m>` → `requirements.md`, `§<n>` → `design.md`.

Status markers: `[ ]` todo, `[~]` queued, `[-]` in progress, `[x]` done.

## Phase 1 — Specs and steering (commit: "Initial project + specs")

- [x] 1.1 Write `requirements.md` (EARS, R1–R15, NFRs, properties P1–P6).
- [x] 1.2 Write `design.md` (architecture, data model, algorithm, API, properties mapping).
- [x] 1.3 Write this `tasks.md`.
- [x] 1.4 Write steering: `product.md`, `architecture.md`, `coding-standards.md`, `testing.md`, `security.md`.
- [x] 1.5 Fill README overview/architecture sections.

## Phase 2 — Database + backend (commit: "Database + backend")

- [x] 2.1 Backend scaffold: `pyproject.toml` (ruff, black line 100, pytest, coverage), pinned `requirements.txt` / `requirements-dev.txt`, `app/main.py` `create_app()`. _§2, §3.2_
- [x] 2.2 `core/config.py` Settings with every variable in §13.1; fail fast without `DATABASE_URL`; update `.env.example`. _R13.1_
- [x] 2.3 `core/logging.py`, `core/middleware.py` (RequestIdMiddleware, BodySizeLimitMiddleware 5 MB), `core/clock.py` (SystemClock/FixedClock). _R12.5, §8.1, §14_
- [x] 2.4 `core/errors.py` AppError hierarchy + handlers producing the envelope (`/api/health` exempt); 500 never leaks details. _R12.2, R12.3, §8.2, §14_
- [x] 2.5 Models for `users (incl. seed_key), skills, user_skills, jobs, job_skills, user_job_states, applications, activity_events` with all constraints and indexes (portable JSON variant, `UTCDateTime` for every timestamp + SQLite round-trip test). _§4, §4.1, NFR2_
- [x] 2.6 Alembic setup + hand-written `0001_initial` migration (stable constraint names, downgrade). _§4.3_
- [x] 2.7 `core/database.py` session factory + `get_session`; `core/deps.py` `get_current_user` (X-Demo-User or `seed_key='demo'`, 401/503); `tests/conftest.py` sets `DATABASE_URL` before importing the app. _R13.2, R13.2a, R13.3, R13.4, §13.2, §16_
- [x] 2.8 Repositories: user, skill (`get_or_create_many` by normalized name), job (SQL filters, search), job_state, application, activity — every per-user query takes `user_id`. _§3.1, §4.2_
- [x] 2.9 `services/matching/skill_catalog.py` + `normalization.py` (`normalize_skill` idempotent loop, `normalize_skills`, `display_skill`, `AMBIGUOUS_RESUME_TERMS`) + idempotence tests — needed by profile storage and ingestion. _R1.3, R3.2, §5.1, §9.1_
- [x] 2.10 Profile schemas (all §8.1 rules) + `ProfileService` + `GET/PUT /api/profile` (full replace, activity event). _R1.1–R1.7_
- [x] 2.11 `application_status.py` state machine (statuses, transition table, `transition()`, SUBMITTED set). _R5.2, R5.4, R5.5, §6_
- [x] 2.12 `ApplicationService` + schemas + routes: create, list (status filter, job summary), PATCH (transitions, applied_at side effect), DELETE, `/applications/meta`, activity events. _R5.1–R5.10, R5.12_
- [x] 2.13 Job schemas + `JobService` list/detail (search, filters, sort for non-score keys, pagination, flags, application status) + bookmark/hide PUT/DELETE + `POST /jobs/{id}/apply` (201 created / 200 transitioned or already Applied / 409). _R2.1–R2.13, §6, §8.3_
- [x] 2.14 Ingestion: `sources.py` (HttpFetcher guards, Remotive, Arbeitnow, Payload, Fixture), `normalizers.py`, `service.py` (dedupe/update/fingerprint across all sources, single transaction, fallback with `seed`/`fixture` source values) + `POST /api/jobs/ingest`. _R10.1–R10.9, R2.14, §11_
- [x] 2.15 Seed data files (`data/seed_profile.json`, `seed_jobs.json` ≥ 30, `seed_applications.json` ≥ 10 across ≥ 6 statuses, relative dates) + `SeedService` (demo user by `seed_key`) + `python -m app.cli seed|ingest`. _R11.1–R11.3, §12_
- [x] 2.16 `GET /api/health` (DB probe; 200 ok / 503 degraded health body with `version`). _R12.6_
- [x] 2.17 `docker-compose.yml` `db` (loopback-only port) + `backend` services (`DATABASE_URL` pointing at `db`), backend Dockerfile + entrypoint (migrate → seed → serve). _R11.4, §18_
- [x] 2.18 Unit/integration/API tests for 2.1–2.16 (SQLite default; `TEST_DATABASE_URL` override); ruff + black clean.

## Phase 3 — Frontend (commit: "Frontend")

- [x] 3.1 Vite + React + TS strict scaffold, pinned deps, Tailwind tokens, ESLint (jsx-a11y) + Prettier, Vitest setup. _§2, §15.1_
- [x] 3.2 `api/client.ts` (ApiError from envelope) + typed endpoint modules + `types/api.ts` mirroring §8. _R12.2, R14.6_
- [x] 3.3 Hooks with TanStack Query + `queryKeys.ts` and the invalidation map. _§15.2, R6.3_
- [x] 3.4 App shell: sidebar (collapsible), top bar, routes, toasts, NotFound. _R14.1, R14.3_
- [x] 3.5 UI kit: Button, Card, Badge, inputs, Dialog, Skeleton, EmptyState, ErrorState (retry), Tabs — labelled and focus-visible. _R14.2, R14.4_
- [x] 3.6 Profile page: full form for every R1.1 field, list editors for skills/projects/education/certifications, server validation errors shown per field. _R1.1–R1.5_
- [x] 3.7 Jobs page: URL-synced search (debounced), filters, sort (non-score keys), pagination, JobCard with skill badges, bookmark/hide/mark-applied actions (score display lands in 4.9). _R2.2–R2.11_
- [x] 3.8 Job detail page: full job info, actions, application status. _R2.1, R2.12_
- [x] 3.9 Applications page: table view + Kanban board (8 columns from meta, HTML5 drag-and-drop, keyboard "Move to" menu, allowed moves only), create/edit dialog for notes, dates, recruiter, outcome, delete confirm. _R5.1, R5.4, R5.7–R5.11_
- [x] 3.10 Dashboard page: stat cards, status breakdown / applications-over-time charts (Recharts), upcoming deadlines, recent activity, empty states. _R6.1, R6.4, R6.5, R14.7_
- [x] 3.11 Frontend Dockerfile (build → nginx, SPA fallback) + compose `frontend` service. _§18_
- [x] 3.12 Vitest: client error parsing, Kanban allowed moves + keyboard Move-to, JobFilters URL sync, dashboard empty state; ESLint + Prettier clean.

## Phase 4 — Matching engine (commit: "Matching engine")

- [x] 4.1 `matching/types.py` dataclasses + `engine.compute_match` with exact §5.3 rules (Fraction arithmetic, half-up rounding, clamp). _R3.1, R3.3, R3.4, R3.10, R3.11_
- [x] 4.2 Role tokenization, location segments, ordinals, project relevance per §5.3. _R3.3_
- [x] 4.3 Reason templates, ordering, `detail` strings, `MatchExplanation` schema (§5.4–5.5). _R4.1–R4.6_
- [x] 4.4 Wire the engine into `JobService` (score per job, `min_score`, `sort=match_score`) and `GET /jobs/{id}` + `POST /jobs/{id}/match`. _R2.2, R2.4, R2.5, R3.12_
- [x] 4.5 `RecommendationService` + `GET /api/recommendations`. _R7.1–R7.3_
- [x] 4.6 `DashboardService` with pure `compute_metrics` (all §7 metrics incl. matching_jobs, score distribution, top recommendations) + `GET /api/dashboard`. _R6.1–R6.5_
- [x] 4.7 `ResumeService` (extraction §9.1 incl. case-sensitive ambiguous terms, outputs §9.2, suggestion rules §9.3, whitespace-only = empty) + `POST /api/resume/analyze`. _R8.1–R8.8_
- [x] 4.8 Interview: provider protocol, template provider and templates (§10 limits, no-skill technical fallback), optional `LlmEnrichedInterviewProvider` with fallback, `InterviewService` + `GET /api/interview/{job_id}`. _R9.1–R9.6, R15.1–R15.3_
- [x] 4.9 Frontend: `MatchScoreRing`, `MatchExplanationPanel` (`MATCH SCORE: n/100`, `+`/`-` reasons, factor breakdown) on job cards/detail; score on JobCard; score sort + min-score filter; dashboard matching count, score distribution chart, top recommendations. _R4.7, R14.5_
- [x] 4.10 Frontend: Resume analysis page (job picker, optional pasted text, results sections, suggestions with evidence) and Interview prep page. _R8.2, R9.1_
- [x] 4.11 Example-based unit tests for every factor case and reason template, resume rules, interview limits, dashboard metric definitions (FixedClock). _§16_

## Phase 5 — Testing + PBT (commit: "Testing + PBT")

- [x] 5.1 Hypothesis profile registration in `tests/conftest.py` (`max_examples=200`, `derandomize=True`, `deadline=None`); shared strategies for profiles/jobs/skill variants (incl. edge-punctuation variants, casefold-colliding project names and roles, stop-token-only roles) in `tests/property/strategies.py`. _NFR3, §17_
- [x] 5.2 `test_p1_score_is_bounded`. _P1: R3.1, R3.3, R3.4, R4.1, R4.2_
- [x] 5.3 `test_p2_adding_matching_skill_never_lowers_score` + `test_p2_adding_unrelated_skill_changes_nothing`. _P2: R3.5, R3.6_
- [x] 5.4 `test_p3_duplicate_skills_have_no_impact`. _P3: R3.2, R3.7_
- [x] 5.5 `test_p4_missing_required_skills_get_no_credit`. _P4: R3.8, R3.9, R4.3_
- [x] 5.6 `test_p5_match_is_deterministic_and_order_independent`. _P5: R3.10, R3.11, R4.6_
- [x] 5.7 `test_p6_application_always_has_one_valid_status` (pure + RuleBasedStateMachine over the service on SQLite). _P6: R5.2, R5.4, R5.5_
- [x] 5.8 Fill gaps to the coverage gates (backend ≥ 80%, matching ≥ 95%, frontend ≥ 60% of components/lib); verify job creation, dedup, normalization, score, explanation, application creation, status updates, dashboard metrics, resume analysis, error handling. _NFR6, §16_
- [x] 5.9 Run the API/integration suite once against Postgres via `TEST_DATABASE_URL` (docker `db`) and record the result in `docs/testing.md`. _NFR2_
- [x] 5.10 Write `docs/testing.md` (how to run each layer, properties ↔ requirements table).

## Phase 6 — Kiro automation (commit: "Kiro automation")

- [x] 6.1 `.kiro/hooks/python-format.json` (PostFileSave on `backend/**/*.py` → `ruff format` + `ruff check --fix`; idempotent, no loop).
- [x] 6.2 `.kiro/hooks/ts-format.json` (PostFileSave on `frontend/src/**/*.{ts,tsx}` → `prettier --write` + `eslint --fix`).
- [x] 6.3 `.kiro/hooks/backend-tests.json` (PostFileSave on `backend/app/**/*.py` → relevant pytest; never writes source files) and optional PostTaskExec test hook.
- [x] 6.4 `docs/kiro-workflow.md`: each hook's trigger, matcher, action, rationale, loop avoidance.

## Phase 7 — MCP + Power + custom agents (commit: "MCP + Power + custom agents")

- [x] 7.1 `.kiro/settings/mcp.json` and `.kiro/mcp.json` with the `fetch` server (`uvx mcp-server-fetch`); explain why both exist. _R10.2_
- [x] 7.2 Exercise the MCP fetch → `data/ingest/*.json` / `source=payload` → `POST /api/jobs/ingest` flow; record the result or the fallback in `docs/kiro-mcp.md`. _R10.2, R10.6, R10.9_
- [x] 7.3 Postman Power: `docs/postman/InternPilot.postman_collection.json` + environment covering every §8 endpoint; `docs/kiro-powers.md` (why Postman, Supabase rejected, review third-party Powers).
- [x] 7.4 Custom Power `.kiro/powers/career-data-toolkit/` (`plugin.json`, skills `job-normalization`, `resume-analysis`, `match-explanation`, `references/scoring-rules.md` exactly matching §5).
- [x] 7.5 Custom agents `.kiro/agents/{architect,backend,frontend,qa,ingestion}-agent.json` with role-restricted tools, steering resources, selective MCP/Powers; `docs/kiro-agents.md`.

## Phase 8 — Final polish (commit: "Final polish")

- [x] 8.1 `docker compose up` end-to-end check: migrations, seed, API, frontend; record evidence. _R11.4_
- [x] 8.2 README complete (requirements, install, env, DB, migrations, seed, run, tests, hooks, MCP, Powers, agents, demo account, architecture).
- [x] 8.3 `docs/architecture.md`, `docs/api.md` (incl. demo-identity warning), `docs/demo.md`, `docs/DEMO_SCRIPT.md`, `docs/KIRO_CHALLENGE_EVIDENCE.md`. _R13.5_
- [x] 8.4 Final audit against the brief's quality bar: all tests and property tests pass, lint clean, no secrets committed, every box above ticked.
