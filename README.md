# InternPilot AI
### AI-Powered Internship & Career Command Center

InternPilot AI helps students and fresh graduates discover internships and entry-level roles, see a transparent 0–100 match score with clear reasons for every job, track applications on a table or Kanban board, prepare for interviews, and compare their resume against a specific role. Matching is deterministic and works fully offline on seeded data; an optional LLM provider can be enabled through environment variables.

## Overview

| Module | What it does |
|---|---|
| Career dashboard | Jobs discovered, matching jobs (score ≥ 60), applications submitted, interviews, offers, response rate, upcoming deadlines, recent activity, top recommendations, charts. |
| Profile | Skills, target roles, locations, work modes, experience, education, projects, certifications, resume text and links, persisted in PostgreSQL. |
| Job discovery | Search, filters, sorting (including by match score), pagination, bookmark, hide, mark as applied. |
| Explainable matching | Deterministic score from eight weighted factors (required skills 35, preferred 10, role 15, experience 15, location 10, work mode 5, education 5, projects 5) with a `match_explanation` listing every `+`/`-` reason. |
| Application tracker | Eight statuses (Saved → Offer/Rejected/Withdrawn) with an enforced transition table, notes, dates, recruiter contact, outcome; table and Kanban views. |
| Resume analysis | Matching and missing skills, relevant projects, missing keywords and rule-based suggestions tied to measurable gaps. It never rewrites your resume. |
| Interview prep | Role, technical, skill, project and HR questions plus prioritized prep topics from deterministic templates, behind a provider interface. |
| Job ingestion | Public no-auth APIs (Remotive, Arbeitnow), MCP-captured payloads or local fixtures, with validation, dedupe and automatic fixture fallback. |

The project is built spec-first with Kiro. Behavior is defined in [`.kiro/specs/internship-intelligence/`](.kiro/specs/internship-intelligence/) (requirements → design → tasks), and project rules live in [`.kiro/steering/`](.kiro/steering/).

## Tech Stack

- **Frontend:** React 18, TypeScript (strict), Vite, Tailwind CSS, React Router, TanStack Query, Recharts
- **Backend:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, httpx
- **Database:** PostgreSQL 16 (SQLite is used only as the default test database)
- **Testing:** Pytest, Hypothesis (property-based), Vitest + Testing Library
- **Quality:** Ruff, Black, ESLint, Prettier
- **Infrastructure:** Docker, Docker Compose, nginx for the built frontend

## Quickstart (docker compose)

Added once the containers are built (spec task 8.1). The target flow is `docker compose up`, which runs migrations and the idempotent seed before starting the API and the frontend.

## Local Dev

Commands are added as each layer lands (spec tasks 2.x and 3.x).

## Testing

See [`.kiro/steering/testing.md`](.kiro/steering/testing.md) for the test layout and coverage gates. The property-based tests for the matching engine will run with `pytest backend/tests/property -v`.

## Kiro Challenge Evidence

| Lesson | Where |
|---|---|
| 1 Specs | `.kiro/specs/internship-intelligence/{requirements,design,tasks}.md` |
| 2 Steering | `.kiro/steering/{product,architecture,coding-standards,testing,security}.md` |

The full evidence table is in `docs/KIRO_CHALLENGE_EVIDENCE.md` (added in the final phase).

## Demo Account

There is one seeded demo user, initially `demo@internpilot.dev` (set by `DEMO_USER_EMAIL`). Requests act as this user by default (it is found by a stable seed key, so editing the profile email is safe), or as the user named in the `X-Demo-User` header. **This is not production authentication.** Do not expose it on a public network.

Under docker compose, PostgreSQL is published on `127.0.0.1:5432` only (for a host-run backend or `TEST_DATABASE_URL`); the backend container reaches it as `db:5432`.

## Architecture

```
React SPA ──REST/JSON /api──► FastAPI
                               ├─ api/routes      HTTP only: validate, call one service
                               ├─ services        business rules, transactions
                               │   ├─ matching    pure deterministic scoring engine
                               │   ├─ ingestion   sources → normalize → validate → dedupe
                               │   └─ interview   provider interface (templates, optional LLM)
                               ├─ repositories    all SQLAlchemy queries, user-scoped
                               └─ models          ORM + constraints ──► PostgreSQL
```

- **One scoring engine.** Job lists, job detail, recommendations, the dashboard and resume analysis all call `compute_match`, so a job never shows two different scores.
- **Layering.** Dependencies point one way: `api → services → repositories → models`. Route handlers and React components contain no business logic.
- **Invariants in the right layer.** Application status is checked by the API schema, the service state machine and a database check constraint. Job dedupe uses `UNIQUE(source, external_id)` plus a normalized title/company/location fingerprint.
- **Offline first.** The app starts and serves every feature without network access, MCP or an LLM. Public job sources fall back to local fixtures.
- **Configuration.** Everything is set through environment variables. See [`.env.example`](.env.example).

Detailed design: [`.kiro/specs/internship-intelligence/design.md`](.kiro/specs/internship-intelligence/design.md).

## License

MIT. See [LICENSE](LICENSE).
