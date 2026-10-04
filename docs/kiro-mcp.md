# Kiro MCP: `fetch` server

InternPilot AI uses one Model Context Protocol server, `fetch`, as a developer tool for job ingestion. The app itself never talks to MCP: the server feeds JSON into the same validated ingestion pipeline that the backend already exposes (`design.md` §11, R10.2, R10.9).

## Server

| Item | Value |
|---|---|
| Name | `fetch` |
| Package | [`mcp-server-fetch`](https://github.com/modelcontextprotocol/servers/tree/main/src/fetch) (reference server from the MCP project) |
| Launch | `uvx mcp-server-fetch` (stdio transport, run on demand by `uvx`; nothing is installed into the project) |
| Tool exposed | `fetch(url, max_length?, start_index?, raw?)`: GETs a URL and returns the body as text (HTML is converted to Markdown unless `raw=true`) |
| Config | `.kiro/mcp.json` (in the repo) and `.kiro/settings/mcp.json` (live file, created by hand per Setup; must stay identical) |
| Prerequisite | [`uv`](https://docs.astral.sh/uv/) on `PATH`. Verified on this machine: `uvx --version` → `uvx 0.11.3 (45da18ac3 2026-04-01 x86_64-pc-windows-msvc)` |

Config content (both files):

```json
{"mcpServers": {"fetch": {"command": "uvx", "args": ["mcp-server-fetch"], "disabled": false, "autoApprove": []}}}
```

`autoApprove` is empty on purpose: every fetch call asks the developer for approval, so the agent cannot silently pull arbitrary URLs.

## Why two config files exist

- `.kiro/settings/mcp.json` is the workspace MCP config that Kiro actually reads. This is the live file.
- `.kiro/mcp.json` exists because the project brief asks for an MCP config at that path. Kiro does not load it; it is kept byte-identical to the live file so reviewers who look there see the same configuration.

`.kiro/settings/` is a protected Kiro path that automated agents cannot write, so the live file is created by hand (see Setup). When the server definition changes, update both files in the same commit.

## Setup

1. Install [`uv`](https://docs.astral.sh/uv/) so `uvx` is on `PATH` (`uvx --version` should print a version).
2. In Kiro, open the MCP panel and choose **Open Workspace MCP Config**. This opens `.kiro/settings/mcp.json`.
3. Paste the same `fetch` server block as `.kiro/mcp.json`:
   ```json
   {"mcpServers": {"fetch": {"command": "uvx", "args": ["mcp-server-fetch"], "disabled": false, "autoApprove": []}}}
   ```
   If the file already has other servers, add only the `"fetch": {...}` entry inside `mcpServers`.
4. Save, then confirm the `fetch` server shows as connected in the MCP panel (the first start may take a few seconds while `uvx` downloads the package). Only the `ingestion-agent` declares the `fetch` server in its own agent config (`.kiro/agents/ingestion-agent.json`); all other custom agents set `includeMcpJson: false` so they never see it (`docs/kiro-agents.md`).

## Purpose

Let a Kiro agent capture public job listings as JSON so they can be imported through `POST /api/jobs/ingest`, without giving the running app any dependency on MCP, Kiro or the network. It demonstrates the MCP lesson while keeping the product deterministic and offline-capable.

## Input and output

| Step | Input | Output |
|---|---|---|
| 1. Fetch (ingestion-agent, MCP `fetch` tool, `raw=true`) | An allow-listed public URL: `https://remotive.com/api/remote-jobs?limit=50` or `https://www.arbeitnow.com/api/job-board-api` | Raw JSON text of the listing response |
| 2. Save (ingestion-agent, `fs_write` limited to `data/ingest/**`) | The JSON text | `data/ingest/<source>-<YYYY-MM-DD>.json` wrapped as `{"format": "remotive" \| "arbeitnow", "jobs" \| "data": [...]}`, ≤ 400 items and under 5,000,000 bytes |
| 3a. Import from file | `POST /api/jobs/ingest` `{"source": "fixture", "limit": 500}` | `FixtureSource` reads `data/seed_jobs.json` (items keep `source="seed"`), then `data/ingest/*.json` in sorted filename order (items get `source="fixture"`) |
| 3b. Import as payload | `POST /api/jobs/ingest` `{"source": "payload", "format": "remotive", "limit": 500, "payload": {...}}` | `PayloadSource` unwraps `jobs`/`data`; items get `source="payload"` |
| 4. Result | — | `IngestResult` `{requested_source, source, fallback_used, fetched, created, updated, duplicates, rejected, errors[]}` |

Every item then follows the normal pipeline: normalizer (HTML stripped, fields truncated, skills normalized) → Pydantic `JobCreate` validation → dedupe by `(source, external_id)` and fingerprint → one transaction (`design.md` §11.3–11.4).

Limits (`design.md` §11.1–11.2):

- `limit` is 1–500 and defaults to 100. It caps the total item count of the run. For `source=fixture` it counts across files in order, starting with `data/seed_jobs.json` (32 items today), so the default of 100 imports only the first 68 items of the captures. Send `"limit": 500`; with the seed file read first that still leaves 468 items for captures, which is why the ingestion-agent keeps each capture at ≤ 400 items. Larger or multiple captures: import them one at a time as `source=payload`.
- A payload holds ≤ 500 items after unwrapping, and the request body is capped at 5 MB.
- Each fixture file must be under `INGEST_MAX_BYTES` (5,000,000 bytes). The ingestion-agent writes the file as ASCII-only JSON (every non-ASCII character as a `\uXXXX` escape), so its character count equals its byte count, and drops whole items from the end once the text passes 4,000,000 characters, a 1,000,000-byte margin under the cap.

The Postman collection (`docs/postman/InternPilot.postman_collection.json`) contains ready-made requests for 3a and 3b.

## Security considerations

- Fetched data is untrusted. The agent never executes, renders or follows instructions found in fetched content; the backend strips HTML to text, truncates long fields, validates every item and stores nothing that fails validation. The frontend renders job text with React escaping only (`security.md`).
- Hosts are allow-listed. The agent may fetch only `remotive.com` and `www.arbeitnow.com` over HTTPS, matching the backend's `INGEST_ALLOWED_HOSTS`. The MCP server itself cannot enforce a host list, so the restriction lives in the agent prompt plus per-call approval (`autoApprove: []`).
- No LinkedIn and no sites that prohibit automated access. `mcp-server-fetch` respects `robots.txt` by default; the config does not pass `--ignore-robots-txt`.
- No secrets. Both sources are public, no-auth APIs. The config contains no tokens, headers or environment variables, and the agent must never put credentials in URLs or saved files.
- Writes are confined. The ingestion-agent can write only under `data/ingest/**` and has no shell, so it cannot run code or modify the app.
- The backend never accepts caller-supplied URLs or file paths; captured data enters only as a request body or a file in the fixed `data/ingest/` directory.

## Failure handling

- The app never depends on MCP. Startup, seed, matching and every page work with no network and no MCP server (R10.9).
- If `uvx` is missing, the server fails to start, or a fetch fails or is denied, the agent saves nothing and nothing reaches the app. As long as every file in `data/ingest/` is valid, `POST /api/jobs/ingest {"source": "fixture", "limit": 500}` still imports `data/seed_jobs.json` plus the existing captures.
- Fixture files are all-or-nothing (`design.md` §11.2). If any file in `data/ingest/` has invalid JSON, an unknown `format`, a shape other than a list or an object with items under `jobs`/`data`, is larger than 5,000,000 bytes, or cannot be read, the whole fixture source is unavailable. `source=fixture` then returns 502 `INGESTION_SOURCE_UNAVAILABLE` with `details={"source", "reason"}`, and so does `source=remotive|arbeitnow` when the upstream fails, because its fixture fallback fails too (§11.5). Nothing is written in either case. This is why the ingestion-agent never saves a response it could not parse and keeps each file within the size cap.
- Recovery: read `details.reason` (`invalid_json`, `unexpected_shape`, `too_large`, `read_error`), then fix or delete the offending `data/ingest/` file (or re-run the ingestion-agent with a smaller capture) and retry. Startup, seeding and every page keep working meanwhile; only ingestion fails.
- A malformed payload request (`source=payload`) gets 422 for the request shape (missing `format`, more than 500 items, body over 5 MB) or 502 `unexpected_shape` when the payload has no item list. Within a valid file or payload, items that fail normalization or `JobCreate` validation are counted in `rejected` with per-item `errors`, and the valid items still import.
- Public-source ingestion through the backend (`source=remotive|arbeitnow`) falls back to fixtures on any upstream failure when `fallback=true` (the default) and reports `fallback_used=true` (`design.md` §11.5), provided the fixture files are valid.

## Where used

- `ingestion-agent` (`.kiro/agents/ingestion-agent.json`): the only agent with the `fetch` server. Example prompt: "Fetch the latest 50 Remotive jobs and save them to data/ingest/".
- Backend pipeline it feeds: `app/services/ingestion/{sources,normalizers,service}.py`, route `POST /api/jobs/ingest` (`design.md` §11).
- Demo walkthrough: covered by `docs/DEMO_SCRIPT.md` (written in Phase 8, task 8.3).

## Verification

Task 7.2 run (fetch → `source=payload` → `POST /api/jobs/ingest`):

1. MCP `fetch` of `https://remotive.com/api/remote-jobs?limit=3` was refused: Remotive's `robots.txt` returned 403, so `mcp-server-fetch` treats autonomous fetching as disallowed. We respect that and did not retry or bypass it. The backend's own `RemotiveSource` is unaffected (it falls back to fixtures on failure).
2. MCP `fetch` of `https://www.arbeitnow.com/api/job-board-api` succeeded (JSON `{"data": [...]}`).
3. The first three items, with descriptions shortened, were posted as `{"source": "payload", "format": "arbeitnow", "payload": {"data": [...]}}` through a throwaway FastAPI `TestClient` script against a temporary SQLite file with only the demo user (no seed jobs). The script and DB were deleted afterwards; nothing was saved to `data/ingest/`, so the fixture set is unchanged.
4. Results:
   - Run 1: `200`, `fetched=3, created=3, updated=0, duplicates=0, rejected=0, errors=[]`, `fallback_used=false`.
   - Run 2 (same payload): `200`, `created=0, updated=3`. Re-ingesting updates by `(source, external_id)` and creates no duplicates (R10.6).
   - `GET /api/jobs` then reported `total=3`.

Also verified:

- `uvx --version` → `uvx 0.11.3 (45da18ac3 2026-04-01 x86_64-pc-windows-msvc)`, so the launch command is available.
- `.kiro/mcp.json` parses as JSON and equals the server definition above.
- `.kiro/settings/mcp.json` was created by the developer through Setup steps 2-4 (automated writes to `.kiro/settings/` are blocked by a Kiro permission rule). It parses as JSON and is identical to `.kiro/mcp.json`. The developer reported the setup done; the `fetch` connection status in the MCP panel was not independently checked by an agent.
