# Kiro Powers

InternPilot AI uses two Powers: the trusted registry Power `postman` for API contract testing, and a project-local custom Power `career-data-toolkit` that packages the matching and resume knowledge.

## Trusted Power: `postman`

| Item | Value |
|---|---|
| Name | `postman` |
| Source | Kiro Powers registry (curated partner Power), installed in this Kiro |
| Other installed Powers | aws-devops-agent, elevenlabs, figma, firebase, supabase-hosted (not used) |
| Artifacts | `docs/postman/InternPilot.postman_collection.json`, `docs/postman/InternPilot.postman_environment.json` |
| MCP server | Hosted streamable-HTTP server `https://mcp.postman.com/minimal` (`@postman/postman-mcp-server`, minimal mode), OAuth sign-in in the browser on first use, no API key |
| Used by | `qa-agent` (`.kiro/agents/qa-agent.json`, which declares the server in its own `mcpServers`) and developers running contract checks in the Postman app |

### Why selected

The product is a REST/JSON API with a strict contract (`design.md` §8): exact response schemas, one error envelope, specific status codes (201 vs 200 on mark-applied, 409 transitions, 413, 422) and an `X-Request-ID` header. Postman is the standard tool for exercising and sharing that kind of contract, and the Power lets Kiro work with collections and environments directly instead of hand-written curl scripts.

### What it accelerates

- API contract testing of the FastAPI endpoints: each request carries test scripts for the status code and body shape, and a collection-level script checks `X-Request-ID` plus the `{"error": {"code", "message", "details"}}` envelope on every non-health error.
- Collection and environment management: one collection covers every §8 endpoint with example bodies; the environment holds only `baseUrl` (`http://localhost:8000`) and `demoUser` (`demo@internpilot.dev`), no secrets.
- Running the collection: the folders run top to bottom as a scenario (list jobs → create application → move → invalid move → duplicate → mark applied → delete → cleanup), so a single run checks the tracker's state machine end to end.

### Side effects of a full run

Only the application chain cleans up after itself (the application it creates is deleted at the end). Everything else changes the demo database:

- "Ingest - MCP payload" inserts a `payload` job (`Example Labs`, external id `900001`); later runs update it instead of adding a duplicate.
- "Ingest - fixtures" and "Ingest - Remotive with fallback" (which falls back to fixtures offline) import `data/seed_jobs.json` plus `data/ingest/*.json`, update existing rows and write a `jobs_ingested` activity event each (if any `data/ingest/` file is invalid or over 5,000,000 bytes, the fixtures request returns 502, and so does the Remotive request whenever it has to fall back; see `docs/kiro-mcp.md` Failure handling). With network access, the Remotive and "Arbeitnow without fallback" requests import live listings; offline, Arbeitnow returns 502.
- Bookmark and hide requests write `job_bookmarked` / `job_hidden` activity events; the remove/unhide requests clear the flags but the events stay.
- "Replace profile" sends the profile captured by "Get profile" earlier in the same run and writes a `profile_updated` event. Run on its own, it overwrites the demo profile with the example body.

`python -m app.cli seed` never overwrites an existing demo user (design.md §12), so re-seeding does not undo these changes. To get back to a clean demo state, drop the database volume and start again (`docker compose down -v ; docker compose up`), which deletes all local data.

### Where used

- `qa-agent` checks the collection against design.md §8 and analyses Collection Runner results (example prompt: "Check that the collection covers every §8 endpoint, then explain the failures in these Collection Runner results").
- Local runs happen in the Postman app: File → Import both files from `docs/postman/`, select the `InternPilot Local` environment, open the Collection Runner. The Power's `runCollection` tool executes in Postman's cloud, which cannot reach `http://localhost:8000`, so it is not used for local runs.
- The backend's own `pytest backend/tests/api` remains the authoritative test suite; the collection is a black-box check of a running server (Docker or local).

### Activation status and tools

This session has no `kiro_powers` tool, so the Power was not activated from here and no Postman sign-in happened. The installed Power's definition (`~/.kiro/powers/installed/postman/POWER.md` and `mcp.json`) was read instead. It exposes 40 tools in minimal mode:

| Group | Tools |
|---|---|
| Workspaces | `createWorkspace`, `getWorkspace`, `getWorkspaces`, `updateWorkspace` |
| Collections | `createCollection`, `getCollection`, `getCollections`, `putCollection`, `duplicateCollection`, `createCollectionRequest`, `createCollectionResponse` |
| Environments | `createEnvironment`, `getEnvironment`, `getEnvironments`, `putEnvironment` |
| Mock servers | `createMock`, `getMock`, `getMocks`, `updateMock`, `publishMock` |
| API specs | `createSpec`, `getSpec`, `getAllSpecs`, `getSpecDefinition`, `updateSpecProperties`, `createSpecFile`, `getSpecFile`, `getSpecFiles`, `updateSpecFile` |
| Generation and sync | `generateCollection`, `generateSpecFromCollection`, `getGeneratedCollectionSpecs`, `getSpecCollections`, `syncCollectionWithSpec`, `syncSpecWithCollection` |
| Execution | `runCollection` |
| User and metadata | `getAuthenticatedUser`, `getTaggedEntities`, `getStatusOfAnAsyncApiTask`, `getEnabledTools` |

The Power's onboarding asks for a `fileEdited` hook that runs the collection on every source change. It was not created: hooks are deferred (Phase 6), and a hook that uploads and runs the collection on each save would send project data to Postman's cloud without a per-action decision.

Ground rule: no remote workspaces, collections, environments, mocks or specs are created, and nothing is uploaded, without explicit user approval for that action. In `qa-agent` every `@postman` call needs approval, and its prompt allows only the read-only `get*` tools by default.

### Considered and rejected: `supabase-hosted`

Supabase provides hosted PostgreSQL plus auth and storage. It was rejected because InternPilot AI runs a self-hosted PostgreSQL 16 container through `docker compose`, must be fully demoable offline from seeded data, and has no need for hosted auth (single demo user by design). Adding a hosted database Power would add an external dependency the architecture deliberately avoids.

### Reviewing third-party Powers

Powers can bundle MCP servers that run code locally and reach external services. Before installing any Power that is not from the curated registry:

- Read its `plugin.json`/`POWER.md`, every `SKILL.md` and its `mcp.json`; know which commands it launches and which hosts it contacts.
- Check what credentials it asks for and where they are stored; never paste secrets into Power files or prompts.
- Prefer Powers with a public source repository and pinned versions.
- Enable it only for the agents that need it (see `docs/kiro-agents.md`).

## Custom Power: `career-data-toolkit`

| Item | Value |
|---|---|
| Location | `.kiro/powers/career-data-toolkit/` |
| Manifest | `plugin.json` (Agent Plugins 1.0.0 format, Kiro fields under `extensions`) plus a legacy `POWER.md` overview |
| Skills | `job-normalization`, `resume-analysis`, `match-explanation` (each `skills/<name>/SKILL.md`) |
| Reference | `references/scoring-rules.md`, a copy of `design.md` §5.1–5.6 (weights, factor rules, rounding, reason templates, explanation shape) |
| Version | `1.0.0` (tracks matching `algorithm_version` `1.0.0`) |

### What it is for

The Power gives agents engineering knowledge, not app logic. All behavior lives in project code (`app/services/matching/`, `app/services/ingestion/`, `app/services/resume_service.py`); the Power tells an agent how that code is supposed to behave, which files implement it, which tests cover it and which mistakes to avoid.

| Skill | Use it when | Covers |
|---|---|---|
| `job-normalization` | Writing or changing ingestion normalizers, seed jobs, skill aliases | Skill normalization steps, aliases, Remotive/Arbeitnow/normalized mappings, employment type and experience inference, fingerprint dedupe |
| `resume-analysis` | Changing resume skill extraction, suggestions or keywords | Whole-word extraction, ambiguous short terms, outputs, suggestion rules and their order, no-rewrite rule |
| `match-explanation` | Changing scoring, reasons or anything that displays a score | Factor rules, exact `Fraction` arithmetic and rounding, reason templates and ordering, `match_explanation` shape, P1–P5 properties |

### How it is used

- Activation: Kiro loads the Power when a prompt mentions its keywords (skill normalization, job normalization, match score, match explanation, resume analysis, internship, career data). It can also be installed explicitly from the Powers panel as a local-directory Power pointing at `.kiro/powers/career-data-toolkit`.
- `backend-agent` lists the three skills and `scoring-rules.md` as resources, so it always has them when editing the backend.
- Example: "Add `svelte` to the skill catalog" → the `job-normalization` skill says to add a `CATALOG` entry, keep every alias value a fixed point, and run `pytest backend/tests/unit/test_skill_catalog.py backend/tests/property -v`.
- `backend-agent` can write only `backend/**`. A scoring-rule change is proposed to the architect-agent or the user, who updates `design.md`, `algorithm_version` and `scoring-rules.md` together.
- Keeping it honest: `design.md` §5.6 requires `algorithm_version` bumps and `references/scoring-rules.md` updates in the same commit as any scoring rule change.

## Installing the Career Data Toolkit Power

The Power is a self-contained folder (`POWER.md` with frontmatter, `plugin.json`, `skills/`, `references/`), so it can be shared as its own public GitHub repository (Bonus lesson 2).

- **From this workspace:** in Kiro, open the Powers panel, choose **Add Custom Power → Import from folder**, and select `.kiro/powers/career-data-toolkit/`.
- **From GitHub:** copy the folder to the root of a public repository, then choose **Add Custom Power → Import from GitHub** and paste the repository URL.
- After install, mentioning a keyword such as "match score" or "resume analysis" loads the matching skill on demand.