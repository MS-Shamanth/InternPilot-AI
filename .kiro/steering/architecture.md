---
inclusion: always
---

# Architecture

Full detail: `.kiro/specs/internship-intelligence/design.md`. This file holds the rules every change must respect.

## System shape

```
React SPA (Vite, TS, Tailwind, React Router, TanStack Query, Recharts)
   │  REST/JSON over /api  (VITE_API_BASE_URL)
FastAPI app (Pydantic v2 schemas)
   │  api → services → repositories → models
SQLAlchemy 2 ORM + Alembic
   │
PostgreSQL 16 (Docker)   ·   SQLite only as the default test database
```

Outbound network is limited to job ingestion (allow-listed hosts) and the optional, disabled-by-default LLM provider. The Kiro MCP `fetch` server is a developer tool that feeds the ingestion endpoint; the app never depends on it.

## Backend layering rules

| Layer | Path | Responsibilities | Must not |
|---|---|---|---|
| API | `app/api/routes/` | Declare routes, bind Pydantic request/response schemas, resolve dependencies (`get_current_user`, `get_session`, `get_clock`), call **one** service method, return its result. | Contain business rules, branch on domain state, run queries, catch domain errors to re-shape them (handlers do that). |
| Services | `app/services/` | Business rules, orchestration, transactions (commit/rollback), activity events, calling engines. | Import FastAPI types (`Request`, `HTTPException`); build SQL directly. |
| Engines | `app/services/matching/`, `application_status.py`, pure helpers | Pure, deterministic functions on dataclasses/enums. | Do I/O, read the clock, use randomness, import models/repositories. |
| Repositories | `app/repositories/` | All SQLAlchemy queries and persistence for one aggregate; per-user queries take `user_id` explicitly. | Contain business rules or commit transactions (services own the unit of work). |
| Models | `app/models/` | ORM mappings and DB constraints. | Contain behavior beyond simple properties. |
| Schemas | `app/schemas/` | Pydantic API contract and validation. | Import models or repositories. |
| Core | `app/core/` | Config, DB session, errors, logging, middleware, deps, clock. | Contain domain logic. |

Dependency direction: `api → services → (engines, repositories) → models`. `schemas` may be used by `api` and `services`. Nothing imports `api`. Cycles are bugs.

## API boundaries

- All endpoints live under `/api`, are REST, JSON-only and documented by FastAPI's OpenAPI.
- Request/response bodies are Pydantic models; ORM objects never leave the service layer as responses.
- Errors always use the envelope `{"error": {"code", "message", "details"}}` from `app/core/errors.py`.
- The frontend reaches the backend only through `frontend/src/api/client.ts`.

## Responsibilities

- **Matching** is one engine (`compute_match`). Job lists, detail, recommendations, dashboard and resume analysis must call it; never re-implement scoring anywhere (including the frontend).
- **Status transitions** are owned by `application_status.transition()`; the UI asks `GET /api/applications/meta` for allowed moves.
- **Dashboard metrics** are computed fresh per request in `DashboardService` (pure `compute_metrics`).
- **Ingestion** = `JobSource` (fetch) → normalizer (map + clean) → Pydantic `JobCreate` (validate) → `IngestionService` (dedupe + persist in one transaction), with fixture fallback.
- **Interview prep** goes through the `InterviewQuestionProvider` protocol; templates are the default.

## Data flow

1. Route validates input → resolves current user and session.
2. Service loads data through repositories, builds engine inputs, calls engines.
3. Service writes changes + activity events, commits once.
4. Route returns the response schema; middleware adds `X-Request-ID`.
5. Frontend hook caches the result; mutations invalidate related query keys.

## Frontend structure rules

- `pages/` compose; `components/` render via props; `hooks/` own data fetching (TanStack Query); `api/` owns HTTP; `lib/` holds formatting helpers; `types/api.ts` mirrors backend schemas.
- No business logic in components: no scoring, no transition rules, no metric math.
- Design tokens live in `tailwind.config.ts`; components use tokens, not ad-hoc hex values.

## Configuration

Everything environment-specific comes from environment variables read by `app/core/config.py` (backend) and `import.meta.env.VITE_*` (frontend). `.env.example` documents every variable with placeholder values.

## Dependency rules

- Pin exact versions in `requirements*.txt` and `package.json`.
- Prefer the standard library and the locked stack; adding a dependency requires a reason in the PR/commit message.
- External integrations (HTTP sources, LLM) sit behind a protocol so tests can substitute fakes.
