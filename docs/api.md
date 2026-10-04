# API

Base URL `http://localhost:8000/api`. JSON only. Interactive docs: `/docs` (OpenAPI at `/openapi.json`). Exact schemas and validation rules: [design.md §8](../.kiro/specs/internship-intelligence/design.md). A Postman collection is in [`postman/`](postman/).

## Demo identity (not authentication)

Requests act as the seeded demo user (found by `seed_key='demo'`), or as the user whose email is sent in the `X-Demo-User` header. Unknown header email → 401 `UNKNOWN_DEMO_USER`; demo user not seeded → 503 `DEMO_USER_NOT_SEEDED`.

**This is not authentication.** Anyone who can reach the API can act as any user. It exists for a single-user local demo; do not deploy it to a public network.

## Endpoints

| Method | Path | Request | Success | Errors |
|---|---|---|---|---|
| GET | `/health` | — | 200 `{status, database, version}` | 503 same body, `degraded` |
| GET | `/profile` | — | 200 `Profile` | 401, 503 |
| PUT | `/profile` | `ProfileUpdate` (full replace) | 200 `Profile` | 409 `EMAIL_TAKEN`, 422 |
| GET | `/jobs` | `q, employment_type[], work_mode[], experience_level[], location, source, skills, min_score, bookmarked, include_hidden, sort, order, page, page_size` | 200 `{items, total, page, page_size, total_pages}` | 422 |
| GET | `/jobs/{id}` | — | 200 `JobDetail` (with `match_explanation`, `application`) | 404 |
| POST | `/jobs/{id}/match` | — | 200 `MatchExplanation` | 404 |
| PUT / DELETE | `/jobs/{id}/bookmark` | — | 200 `JobState` | 404 |
| PUT / DELETE | `/jobs/{id}/hide` | — | 200 `JobState` | 404 |
| POST | `/jobs/{id}/apply` | — | 201 created, 200 moved to / already `Applied` | 404, 409 `INVALID_STATUS_TRANSITION` |
| POST | `/jobs/ingest` | `{source: fixture\|remotive\|arbeitnow\|payload, fallback, limit ≤ 500, format?, payload?}` | 200 `IngestResult` | 413, 422, 502 `INGESTION_SOURCE_UNAVAILABLE` |
| GET | `/recommendations` | `limit` 1–20 (default 5) | 200 `[{job, match_explanation}]` | 422 |
| GET | `/applications` | `status[]` | 200 list (unpaginated, max 500) | 422 |
| GET | `/applications/meta` | — | 200 `{statuses, transitions}` | — |
| POST | `/applications` | `ApplicationCreate` | 201 `Application` | 404, 409 `DUPLICATE_APPLICATION`, 422 |
| PATCH | `/applications/{id}` | `ApplicationUpdate` | 200 `Application` | 404, 409 `INVALID_STATUS_TRANSITION`, 422 |
| DELETE | `/applications/{id}` | — | 204 | 404 |
| GET | `/dashboard` | — | 200 `Dashboard` | — |
| POST | `/resume/analyze` | `{job_id, resume_text?}` | 200 `ResumeAnalysis` | 404, 422 `RESUME_EMPTY` |
| GET | `/interview/{job_id}` | — | 200 `InterviewPrep` | 404 |

Another user's application returns 404, not 403. Unknown body fields and unknown query parameters are 422. Request bodies over 5 MB are 413.

## Error envelope

Every error except `/health` uses:

```json
{"error": {"code": "NOT_FOUND", "message": "Job not found.", "details": null}}
```

- `code` is `UPPER_SNAKE`: `NOT_FOUND`, `VALIDATION_ERROR`, `DUPLICATE_APPLICATION`, `INVALID_STATUS_TRANSITION`, `RESUME_EMPTY`, `INGESTION_SOURCE_UNAVAILABLE`, `PAYLOAD_TOO_LARGE`, `UNKNOWN_DEMO_USER`, `DEMO_USER_NOT_SEEDED`, `EMAIL_TAKEN`, `CONFLICT`, `DATABASE_UNAVAILABLE`, `INTERNAL_ERROR`.
- 422 `details` is a list of `{loc, msg, type}`; raw input is never echoed.
- 500 always says "An unexpected error occurred."; details go to the server log with the request id.
- Every response carries an `X-Request-ID` header.
