# InternPilot AI — Master Build Brief (Kiro University Final Exam)

Source of truth for every workflow step. Read this whole file before doing anything.

## 0. Orchestrator decisions (binding)

- Repo root = workspace root: `C:\Users\MS Shamanth\Desktop\Kiro Uni` (so `.kiro/` hooks/steering/agents/powers are live in Kiro). GitHub repo name will be `internpilot-ai`. Do NOT nest the project in a subfolder.
- OS: Windows, PowerShell. Never use `&&` in PowerShell commands; use `;`. Never run long-running dev servers in the foreground (use background processes or timeouts and stop them afterwards).
- Brand-new git repo. `git init` in the repo root, default branch `main`. Today is 2026-10-03, so the first commit is after 2026-09-21 as required. Commit at each milestone with clear messages (1 Initial project + specs, 2 Database + backend, 3 Frontend, 4 Matching engine, 5 Testing + PBT, 6 Kiro automation, 7 MCP + Power + custom agents, 8 Final polish). Never commit `.env`, secrets, `node_modules`, `.venv`, build outputs, caches. Do NOT push and do NOT modify git config; if git user.name/email is unset, report it instead of setting it. The user will create the GitHub remote and push.
- Specs and steering are written FIRST (Phase 1, commit 1) and then drive implementation. Implementation tasks in `.kiro/specs/internship-intelligence/tasks.md` must be checked off as they are completed.
- Kiro file formats:
  - Hooks: v2 JSON at `.kiro/hooks/<id>.json`, schema `{"version":"v1","hooks":[{"name":..., "trigger":"PostFileSave", "matcher":"<regex on file path>", "action":{"type":"command","command":"..."}}]}`. Valid triggers: PreToolUse, PostToolUse, SessionStart, Stop, UserPromptSubmit, PreTaskExec, PostTaskExec, PostFileCreate, PostFileSave, PostFileDelete. Action types `command` or `agent`. Commands must be Windows/PowerShell-compatible and cross-platform where practical, must not loop (formatters must not re-trigger themselves endlessly — e.g. formatters are idempotent and the test hook must not write source files). Hooks needed: Python format (ruff format + ruff check --fix on backend `.py`), TS format (prettier --write + eslint --fix on frontend `.ts/.tsx`), backend test hook (run relevant pytest on backend source save), plus optionally a PostTaskExec test hook.
  - MCP: Kiro reads workspace MCP config from `.kiro/settings/mcp.json`. Create BOTH `.kiro/settings/mcp.json` (live) and `.kiro/mcp.json` (as the brief requests) with the `fetch` server (`uvx mcp-server-fetch`). Document why both exist.
  - Custom agents: `.kiro/agents/<name>.json` (Kiro agent config: name, description, prompt, tools / allowedTools, resources using `file://` paths to steering docs, mcpServers selectively, welcomeMessage, example prompts). Also add a short markdown description per agent if useful.
  - Custom Power: `.kiro/powers/career-data-toolkit/` with `plugin.json` (name, displayName, description, version, keywords/activation keywords, skills list), `skills/job-normalization/SKILL.md`, `skills/resume-analysis/SKILL.md`, `skills/match-explanation/SKILL.md` (each with YAML front matter name/description), `references/scoring-rules.md`. Scoring rules must exactly match the implemented algorithm.
- Trusted registry Power (Lesson 5): installed Powers in this Kiro are aws-devops-agent, elevenlabs, figma, firebase, postman, supabase-hosted. Selected: **postman** (REST API testing / collection management for the FastAPI endpoints). Produce a Postman collection `docs/postman/InternPilot.postman_collection.json` + environment file covering every endpoint, and document in `docs/kiro-powers.md` (name, why selected, what it accelerates, where used, and that third-party Powers should be reviewed before install). If the step agent has access to the `kiro_powers` tool, activate and use the postman power; if not, generate the collection file and leave a clearly marked section noting the orchestrator will run it through the Power afterwards. Supabase was considered (Postgres) but rejected because the app uses self-hosted Postgres via Docker — record that decision.
- Database: PostgreSQL is the real database (docker compose). For automated tests, if Postgres is not available on the machine, integration/API tests may run against SQLite through the same SQLAlchemy models (keep models portable), with a documented `TEST_DATABASE_URL` override to run them on Postgres. Check whether Docker/Postgres is available and record what was verified.
- Optional LLM: behind an interface, disabled by default via env vars. Core matching/interview/resume logic is deterministic and works without any network.
- Auth: single seeded demo user resolved by a lightweight dependency (e.g. `X-Demo-User` header or default demo user). Document it; flag in docs that it is not production auth.
- Pin dependency versions (exact versions in requirements.txt / package.json).

## 1. Product: InternPilot AI — AI-Powered Internship & Career Command Center

For students/fresh graduates: discover opportunities, evaluate fit, track applications, prepare for interviews, understand exactly why a role matches. Must look like a serious SaaS portfolio project, not a toy CRUD app, not a generic AI-dashboard look.

### A. Career Dashboard
Total jobs discovered, jobs matching profile, applications submitted, interviews scheduled, offers received, response rate, upcoming deadlines, recent activity, top recommended opportunities. Charts (Recharts).

### B. User Profile
Name, email, location, target roles, preferred locations, experience level, education, technical skills, soft skills, projects, certifications, resume text, GitHub/portfolio/LinkedIn URLs. Editable; persisted in PostgreSQL.

### C. Job Discovery
Fields: title, company, location, internship/full-time type, work mode, required skills, preferred skills, experience, salary/stipend, application URL, deadline, source, description, date discovered. Support search, filters, sorting, pagination, save/bookmark, mark applied, hide. Never scrape LinkedIn or sites prohibiting automation; use public APIs/endpoints or local fixtures. Must fully work on seeded data offline.

### D. AI Job Matching (central feature)
Transparent deterministic score 0–100 per job. Factors: technical skill overlap, role similarity, experience compatibility, location compatibility, education compatibility, work mode, optional project relevance. UI shows `MATCH SCORE: 87/100` plus reasons like `+ React matches required frontend skill`, `- Java experience is missing`. Backend returns a `match_explanation` object (per-factor weights/points, positive and negative reasons, matched/missing required & preferred skills). No external LLM dependency.

### E. Application Tracker
Statuses: Saved, Interested, Applied, Assessment, Interview, Rejected, Offer, Withdrawn. Move between statuses, notes, interview date, recruiter name/email, application date, deadline, outcome. Table view AND Kanban board (drag-and-drop or accessible move controls). Dashboard reflects application data.

### F. Interview Prep
For a selected job: role-specific, technical, HR, project, required-skill-based questions, suggested prep topics. Deterministic templates behind a service interface so an LLM can be plugged in later.

### G. Resume / Skill Analysis
Compare resume text vs selected job: matching skills, missing skills, relevant projects, missing keywords, suggested improvements, compatibility score. Do not rewrite the resume. Recommendations based on measurable differences.

## 2. Tech stack
Frontend: React + TypeScript + Tailwind + React Router + Recharts (Vite). Backend: Python + FastAPI + Pydantic v2. DB: PostgreSQL + SQLAlchemy 2 + Alembic. Tests: Pytest, Hypothesis, Vitest (+ Testing Library). Quality: Ruff, Black, ESLint, Prettier. Infra: Docker + Docker Compose. REST. Clean modular architecture, service/repository separation, typed interfaces, env-based config. No business logic in route handlers or React components.

## 3. Repository structure
```
frontend/ (src/, public/, tests/, package.json ...)
backend/  (app/{api,models,schemas,repositories,services,core,main.py}, tests/, alembic/, requirements.txt)
data/     (seed_jobs.json, seed_profile.json [+ seed_applications.json])
.kiro/    (steering/, specs/, hooks/, agents/, powers/, settings/mcp.json, mcp.json)
docs/     (architecture.md, api.md, testing.md, demo.md, kiro-workflow.md, kiro-powers.md, kiro-mcp.md, kiro-agents.md, KIRO_CHALLENGE_EVIDENCE.md, DEMO_SCRIPT.md)
docker-compose.yml, .env.example, .gitignore, README.md, LICENSE (MIT)
```

## 4. Kiro Lesson 1 — Specs (BEFORE implementation)
`.kiro/specs/internship-intelligence/{requirements.md,design.md,tasks.md}`. Requirements in EARS form ("WHEN ... THE SYSTEM SHALL ..."), numbered with acceptance criteria, testable. Include e.g.: WHEN a user views a job THE SYSTEM SHALL calculate a compatibility score between 0 and 100; WHEN a job contains required skills THE SYSTEM SHALL compare them against the user's normalized skill set; WHEN a user applies to a job THE SYSTEM SHALL create an application record with status "Applied"; WHEN the user adds a matching skill THE SYSTEM SHALL NOT decrease the resulting job match score. Include at least one requirement complex enough to derive PBTs (the matching properties below). design.md: architecture, data model, algorithm with weights, API, correctness properties mapped to requirements. tasks.md: phased checklist referencing requirement IDs; implementation follows it.

## 5. Kiro Lesson 2 — Steering (`.kiro/steering/`)
- product.md: purpose, target users, UX principles, terminology, constraints.
- architecture.md: React+FastAPI+Postgres, layering rules, API boundaries, repo/service responsibilities, data flow, dependency rules.
- coding-standards.md: TS rules, Python rules, naming, error handling, type safety, component structure, API conventions.
- testing.md: unit/integration/PBT expectations, naming, minimum coverage, determinism.
- security.md: no hard-coded secrets, env vars, input validation, SQL injection protection, safe external API handling, no credentials in git, secure error responses.
Use standard Kiro front matter (`inclusion: always` default; may use `fileMatch` for language-specific ones). All later code must follow them.

## 6. Kiro Lesson 3 — Hooks
See section 0 for format. Document every hook in `docs/kiro-workflow.md` (trigger, matcher, action, why, loop avoidance).

## 7. Kiro Lesson 4 — Property-based tests (Hypothesis), e.g. `backend/tests/property/test_matching_properties.py`
1. Score bounds: 0 <= score <= 100 for all valid profile/job.
2. Matching-skill monotonicity: adding a genuinely matching skill never reduces the score.
3. No duplicate impact: duplicating a skill doesn't increase score.
4. Missing skills: required skills absent from profile get no credit.
5. Determinism: match(p, j) == match(p, j) (including explanation).
6. Status validity: application records always have exactly one valid status (test schemas/state machine/service).
Plus example-based edge-case tests. Easy to locate and demo (`pytest backend/tests/property -v`). Name each test after its property and reference the requirement ID.

## 8. Kiro Lesson 5 — Powers: see section 0 (postman). `docs/kiro-powers.md`.

## 9. Bonus 2 — Custom Power `career-data-toolkit`: see section 0. Knowledge for normalizing job skills, normalizing profile skills, explainable match reasons, resume-to-job comparison. Activation keywords in manifest. App logic stays in project code. Document usage.

## 10. Kiro Lesson 6 — MCP
`fetch` MCP server (uvx mcp-server-fetch). Job-ingestion workflow: fetch public job data (a public no-auth endpoint such as Remotive `https://remotive.com/api/remote-jobs` or Arbeitnow `https://www.arbeitnow.com/api/job-board-api`), normalize, validate (Pydantic), deduplicate, store in Postgres. Backend `POST /api/jobs/ingest` uses an ingestion service with pluggable sources: public HTTP source (httpx, timeout, size limits, allow-listed hosts) and local fixture source fallback; also accept a JSON payload captured via the MCP fetch tool (e.g. `data/ingest/*.json` or request body) so the Kiro-agent MCP workflow can feed data in. App startup must not depend on MCP or network. `docs/kiro-mcp.md`: server, purpose, input/output, security, failure handling, where used. Actually exercise the MCP-style flow if possible and record result; otherwise document the fallback.

## 11. Kiro Lesson 7 — Custom agents (`.kiro/agents/`)
- architect-agent: review architecture/specs/dependencies/maintainability; read-only tools; resources architecture.md, product.md.
- backend-agent: FastAPI/Postgres/SQLAlchemy/services/repos/tests; resources architecture.md, coding-standards.md, testing.md; can use career-data-toolkit power.
- frontend-agent: React/TS UI respecting design system + API contract; resources product.md, architecture.md, coding-standards.md.
- qa-agent: run tests, edge cases, regressions, coverage; resources testing.md, security.md; can use postman power.
- (optional) ingestion-agent with fetch MCP only.
Restrict tools per role; MCP/Powers selectively. Welcome message + useful prompts each. `docs/kiro-agents.md`.

## 12. Database
users(id, name, email unique, location, education, resume_text, github_url, portfolio_url, linkedin_url, created_at, updated_at) + profile fields needed (target_roles, preferred_locations, experience_level, preferred_work_modes, soft_skills, projects, certifications — JSON columns or child tables, keep portable). skills(id, name, normalized_name unique). user_skills(user_id, skill_id). jobs(id, external_id, title, company, location, work_mode, employment_type, description, salary_min, salary_max, application_url, deadline, source, discovered_at, + experience_level, is_hidden/bookmark state per user as needed) with uniqueness: unique(source, external_id) plus a normalized dedupe fingerprint (title+company+location). job_skills(job_id, skill_id, is_required). applications(id, user_id, job_id, status, applied_at, deadline, interview_date, recruiter_name, recruiter_email, notes, outcome, created_at, updated_at) with unique(user_id, job_id) and status check constraint. Alembic migration(s) + seed command.

## 13. API (OpenAPI via FastAPI, consistent error envelope)
GET /api/jobs, GET /api/jobs/{id}, POST /api/jobs/ingest, POST /api/jobs/{id}/match, GET /api/recommendations, GET /api/profile, PUT /api/profile, POST /api/applications, GET /api/applications, PATCH /api/applications/{id}, DELETE /api/applications/{id}, GET /api/dashboard, POST /api/resume/analyze, GET /api/interview/{job_id}, plus bookmark/hide endpoints and GET /api/health. `docs/api.md`.

## 14. Frontend UX
Responsive layout, sidebar nav, dashboard cards, charts, job cards, skill badges, match score visual (ring/gauge), Kanban, search/filter, empty/loading/error states, toasts, modals/dialogs. Cohesive design system (tokens in Tailwind config), accessible (labels, focus states, keyboard-usable Kanban moves, contrast). API client layer + hooks; no business logic in components.

## 15. Seed data
1 demo user, 20+ skills, 30+ realistic jobs (varied companies, locations, skills, experience, work modes, internship/full-time), 10+ applications across statuses. Dashboard meaningful on first start.

## 16. Demo mode
`docker compose up` runs db + backend (runs migrations + idempotent seed on start) + frontend. Also documented local dev commands. README: requirements, install, env setup, DB setup, migration, seed, frontend/backend startup, tests, hooks, MCP setup, Power setup, custom agents usage, demo account, architecture overview.

## 17. Testing requirements
Backend: unit, API, DB/integration, property-based. Frontend: component + core interaction tests (Vitest). Verify at least: job creation, job dedup, skill normalization, match score, match explanation, application creation, status updates, dashboard metrics, resume analysis, error handling.

## 18. Judge docs
`docs/KIRO_CHALLENGE_EVIDENCE.md` table: | Lesson | Evidence | File / Location | How It Is Demonstrated | for 1 Specs, 2 Steering, 3 Hooks, 4 PBT, 5 Powers, 6 MCP, 7 Custom Agents, Bonus 2 Custom Power — exact file paths, unambiguous. Emphasize the chain Spec → Steering → Agent → Power → MCP → Implementation → Hook → PBT.
`docs/DEMO_SCRIPT.md` (5–8 min): dashboard, seeded jobs, open job, match score, reasons, save job, create application, move status, dashboard metrics change, resume analysis, interview questions, run tests, show PBT, show specs, steering, hooks, MCP config, agents, installed Power, custom Power.

## 19. Engineering rules
No hard-coded secrets; no DB logic in frontend; no business logic in route handlers; validate all input; typed schemas; external integrations behind abstractions; deterministic matching; reproducible tests; graceful external API failure; minimal deps; simple over clever; NO placeholder functionality disguised as complete; NO TODOs for core features; don't break existing functionality; run tests after substantial changes; follow steering.

## 20. Final quality bar (verify each, record evidence in the final audit)
Frontend builds/runs, backend runs, migrations work, seed loads, dashboard, job discovery, matching, explainability, applications, Kanban, resume analysis, interview prep, MCP works or falls back, tests pass, property tests pass, hooks configured, steering exists, trusted Power used, custom Power exists, agents exist, README complete, evidence doc complete, demo script complete, .env.example exists, git history clean, no secrets committed.
