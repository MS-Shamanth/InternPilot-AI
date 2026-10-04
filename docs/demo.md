# Demo: running the stack

## Start

```powershell
# Uses the placeholder values in .env.example; no real .env is needed for a local demo.
docker compose --env-file .env.example up -d --build --wait
```

If host port 5432 is taken, set `POSTGRES_PORT` (e.g. `$env:POSTGRES_PORT='55432'`) before running. The backend entrypoint runs `alembic upgrade head`, then the idempotent seed, then uvicorn.

| URL | What |
|---|---|
| http://localhost:5173 | Frontend (nginx, SPA fallback) |
| http://localhost:8000/api/health | Health |
| http://localhost:8000/docs | OpenAPI UI |

Stop and delete the database volume: `docker compose --env-file .env.example down -v`.

All ports bind to `127.0.0.1`. The demo identity is not authentication; do not expose the stack publicly.

## Recorded end-to-end check (task 8.1)

Run on Windows with Docker Desktop (engine 29.3.1), `POSTGRES_PORT=55432` because 5432 was in use on the host.

| Check | Result |
|---|---|
| `up -d --build --wait` | db, backend, frontend all `healthy` |
| Migrations (backend log) | `Running upgrade -> 0001_initial` |
| Seed (backend log) | `user_created=True skills_created=65 jobs_created=32 jobs_duplicates=0 applications_created=13` |
| `GET /api/health` | `{"status":"ok","database":"ok","version":"0.1.0"}` |
| `GET /api/dashboard` | `total_jobs_discovered=32`, `matching_jobs=18`, `applications_submitted=9`, `interviews_scheduled=2`, `offers_received=1`, `response_rate=55.6` |
| `GET /api/recommendations` | 5 items, each `{job, match_explanation}` |
| `GET /api/jobs?page_size=1` | `total=32`, item has `match_score=100` |
| Frontend `/` and `/jobs/1` | 200, `index.html` with `#root` (SPA fallback) |
| `down -v` | containers, network and `internpilot_pgdata` removed |

For a guided walkthrough see [DEMO_SCRIPT.md](DEMO_SCRIPT.md).
