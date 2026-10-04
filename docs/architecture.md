# Architecture

Summary of [design.md](../.kiro/specs/internship-intelligence/design.md); rules every change follows are in [`.kiro/steering/architecture.md`](../.kiro/steering/architecture.md).

```
React SPA (Vite, TS, Tailwind, React Router, TanStack Query, Recharts)
   │  REST/JSON over /api (VITE_API_BASE_URL)
FastAPI (Pydantic v2)   api → services → repositories → models
   │
SQLAlchemy 2 + Alembic ──► PostgreSQL 16 (SQLite only as default test DB)
```

## Backend (`backend/app/`)

| Layer | Path | Role |
|---|---|---|
| API | `api/routes/` | Validate input, resolve user/session/clock, call one service method. |
| Services | `services/` | Business rules, one commit per request, activity events. |
| Engines | `services/matching/`, `services/application_status.py`, `services/resume_analysis.py` | Pure, deterministic functions on frozen dataclasses. |
| Ingestion | `services/ingestion/` | `JobSource` → normalizer → `JobCreate` → dedupe + persist; fixture fallback. |
| Interview | `services/interview/` | `InterviewQuestionProvider`: templates by default, optional LLM enrichment. |
| Repositories | `repositories/` | All queries; per-user queries take `user_id`. |
| Models / schemas | `models/`, `schemas/` | ORM + DB constraints / API contract. |
| Core | `core/` | Config, DB session, errors + envelope, middleware (request id, 5 MB body cap), clock, deps. |

Key decisions:

- **One scoring engine.** `compute_match` (eight weighted factors, `Fraction` arithmetic, half-up rounding) feeds job lists, detail, recommendations, the dashboard and resume analysis.
- **Status invariant in three places.** Pydantic enum, `application_status.transition()` and a DB check constraint.
- **Dedupe.** `UNIQUE(source, external_id)` plus a normalized title/company/location fingerprint.
- **Determinism.** Time comes from an injected `Clock`; no randomness; core features need no network or LLM.
- **Outbound HTTP** only from the ingestion `HttpFetcher` (HTTPS, host allow-list, no redirects, timeout, size cap) and the disabled-by-default LLM provider.

## Frontend (`frontend/src/`)

`pages/` compose, `components/` render props, `hooks/` own TanStack Query data access, `api/` owns HTTP (`client.ts` → `ApiError`), `types/api.ts` mirrors backend schemas, `lib/` holds formatting. No scoring, transition or metric logic in the UI; allowed moves come from `GET /api/applications/meta`.

## Deployment

`docker-compose.yml`: `db` (postgres:16-alpine), `backend` (non-root, entrypoint migrate → seed → uvicorn), `frontend` (nginx-unprivileged, SPA fallback). All ports on `127.0.0.1`. See [demo.md](demo.md).
