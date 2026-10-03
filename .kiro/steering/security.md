---
inclusion: always
---

# Security

## Secrets and configuration

- No hard-coded secrets, tokens, passwords or API keys anywhere in code, tests, fixtures, docs or Docker files.
- All configuration comes from environment variables (`app/core/config.py`, `VITE_*`). `.env.example` contains placeholders only (e.g. `change-me`).
- `.env` and any `*.env` are gitignored and must never be committed. Check `git status` before every commit.
- Secrets are typed `SecretStr` and never logged, echoed in responses or included in error details.
- Frontend env vars are public by nature: never put secrets in `VITE_*`.

## Input validation

- Every request body, path and query parameter is validated by a Pydantic schema with explicit types, lengths, list sizes and enums (`design.md` §8.1). Request models forbid unknown fields.
- Request bodies are capped at 5 MB; ingestion payloads at 500 items.
- URLs accept only `http`/`https`; profile GitHub/LinkedIn URLs are host-checked.
- Validation errors never echo raw input back (`input`/`ctx` stripped).

## SQL injection protection

- All database access goes through SQLAlchemy ORM/Core with bound parameters. Never build SQL with f-strings or `%` formatting; `text()` only with bound parameters and never with user input in the SQL string.
- Search uses `ilike` with a bound parameter; escape `%` and `_` in user-supplied search terms.

## Safe external API handling

- Outbound HTTP only from the ingestion `HttpFetcher` and the optional LLM provider.
- Ingestion: HTTPS only, exact-match host allow-list (`INGEST_ALLOWED_HOSTS`), redirects disabled, timeout (`INGEST_TIMEOUT_SECONDS`), streamed size cap (`INGEST_MAX_BYTES`), JSON-only, every item validated before storage. Never accept caller-supplied URLs or file paths.
- Treat all external data (APIs, MCP payloads, fixtures) as untrusted: strip HTML to text, truncate long fields, never render it as HTML in the frontend (React escaping only; no `dangerouslySetInnerHTML`).
- Never scrape LinkedIn or sites that forbid automated access.
- The LLM provider is off by default, gets only job/profile context needed for questions, has a 15 s timeout, and its output is treated as untrusted text.

## Credentials in git

- Seed data uses placeholder identities (`demo@internpilot.dev`, `recruiter@example.com`).
- Never commit `.env`, keys, database dumps, `node_modules`, virtualenvs or build output.
- If a secret is committed by mistake, rotate it; do not just delete the file.

## Secure error responses

- Errors use the standard envelope; 500 responses say only "An unexpected error occurred." with the request id header — no stack traces, SQL, file paths or config values.
- Full details go to server logs at ERROR with the request id.
- Authorization: every per-user query is scoped by `user_id`; accessing another user's application returns 404 (not 403) to avoid leaking existence.

## Demo identity

The `X-Demo-User` / `DEMO_USER_EMAIL` mechanism is **not authentication**. It exists for a single-user demo and must be documented as such. Do not deploy it to a public network as-is.

## CORS and headers

- CORS allows only `CORS_ORIGINS`; no wildcard with credentials.
- Containers run as a non-root user; the database is not exposed beyond the compose network except the documented local port.
