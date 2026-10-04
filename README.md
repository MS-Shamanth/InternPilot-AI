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

## Requirements

- Docker Desktop / Docker Engine with Compose v2 (for the full stack)
- For local development: Python 3.12, Node.js 22, PostgreSQL 16 (or the compose `db` service)

## Quickstart (docker compose)

```powershell
docker compose --env-file .env.example up -d --build --wait
```

Open http://localhost:5173 (frontend), http://localhost:8000/docs (API). The backend entrypoint runs `alembic upgrade head`, then the idempotent seed (demo user, 32 jobs, 13 applications), then uvicorn. If port 5432 is busy, set `POSTGRES_PORT` first. Stop with `docker compose --env-file .env.example down -v`. Details and the recorded run: [docs/demo.md](docs/demo.md); walkthrough: [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md).

## Environment

All configuration comes from environment variables, documented with placeholders in [`.env.example`](.env.example). For anything beyond a local demo, `cp .env.example .env` and change the values; `.env` is gitignored. `DATABASE_URL` is required. The LLM provider is off by default (`LLM_ENABLED=false`). `VITE_*` values are public and baked into the frontend build.

## Local Dev

Database: run `docker compose --env-file .env.example up -d db` or point `DATABASE_URL` at your own PostgreSQL.

```powershell
# Backend (from backend/)
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # source .venv/bin/activate on macOS/Linux
pip install -r requirements-dev.txt
$env:DATABASE_URL = "postgresql+psycopg://internpilot:change-me@localhost:5432/internpilot"
alembic upgrade head                  # migrations
python -m app.cli seed                # idempotent seed
python -m app.cli ingest --help       # optional: import jobs (fixture fallback)
uvicorn --factory app.asgi:build_app --reload

# Frontend (from frontend/)
npm ci
npm run dev                           # http://localhost:5173
```

## Testing

| What | Command |
|---|---|
| Backend, all layers (SQLite by default) | `pytest` in `backend/` |
| Property-based tests (Hypothesis P1–P6) | `pytest tests/property -v` |
| Backend coverage | `pytest --cov=app --cov-report=term-missing` |
| Backend lint/format | `ruff check .`, `ruff format --check .`, `black --check .` |
| Frontend | `npm run typecheck`, `npm run lint`, `npm run format:check`, `npm test`, `npm run build` |

Set `TEST_DATABASE_URL` to run the backend suite on PostgreSQL. Layout, properties ↔ requirements and the recorded Postgres run: [docs/testing.md](docs/testing.md).

## Kiro

| Feature | Where | Docs |
|---|---|---|
| Specs | `.kiro/specs/internship-intelligence/` | requirements → design → tasks |
| Steering | `.kiro/steering/` | product, architecture, coding standards, testing, security |
| Hooks | `.kiro/hooks/` (format on save, related tests, task tests) | [docs/kiro-workflow.md](docs/kiro-workflow.md) |
| MCP | `.kiro/settings/mcp.json`, `.kiro/mcp.json` (`fetch`) | [docs/kiro-mcp.md](docs/kiro-mcp.md) |
| Powers | Postman (`docs/postman/`), custom `.kiro/powers/career-data-toolkit/` | [docs/kiro-powers.md](docs/kiro-powers.md) |
| Custom agents | `.kiro/agents/` (architect, backend, frontend, qa, ingestion) | [docs/kiro-agents.md](docs/kiro-agents.md) |

Full evidence table: [docs/KIRO_CHALLENGE_EVIDENCE.md](docs/KIRO_CHALLENGE_EVIDENCE.md). API reference: [docs/api.md](docs/api.md).

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

More: [docs/architecture.md](docs/architecture.md) and [`design.md`](.kiro/specs/internship-intelligence/design.md).

## License

MIT. See [LICENSE](LICENSE).
