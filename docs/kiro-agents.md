# Kiro custom agents

Five role-scoped agents live in `.kiro/agents/`. Each one gets only the tools, steering, Powers and MCP servers its role needs. Prompt text is a soft guardrail; the hard limits are `tools`, `toolsSettings` (path and command allow/deny lists) and `mcpServers`.

| Agent | Purpose | Tools | Writes | Shell | Resources | MCP / Powers |
|---|---|---|---|---|---|---|
| `architect-agent` | Review architecture, specs, dependencies, maintainability | `fs_read`, `grep`, `glob`, `code` | none | none | architecture.md, product.md, requirements/design/tasks | none |
| `backend-agent` | FastAPI, SQLAlchemy, services, repositories, migrations, tests | read, `fs_write`, `execute_bash` | `backend/**` | pytest, ruff, black, `alembic upgrade head`, `python -m app.cli seed`, read-only git (exact grammars, `denyByDefault`) | architecture.md, coding-standards.md, testing.md | career-data-toolkit (3 skills + scoring-rules.md) |
| `frontend-agent` | React + TS UI on the API contract | read, `fs_write`, `execute_bash` | `frontend/**` (not `node_modules`, `dist`) | npm test/ci, npm run lint/format/test/build, vitest/eslint/prettier/tsc, read-only git (exact grammars, `denyByDefault`) | product.md, architecture.md, coding-standards.md | none |
| `qa-agent` | Run suites, edge cases, regressions, coverage, security checks | read, `fs_write`, `execute_bash`, `@postman` | `backend/tests/**`, `frontend/tests/**` | check-only test runners and linters, read-only git (exact grammars, `denyByDefault`) | testing.md, security.md, kiro-powers.md | postman Power MCP server (`mcp.postman.com/minimal`), every call approved |
| `ingestion-agent` | Capture Remotive/Arbeitnow listings as JSON | `@fetch`, `fs_write` | `data/ingest/**` | none | security.md, design.md (§11), kiro-mcp.md | `fetch` MCP server (only agent with `fetch`) |

Common rules for all agents:

- `.env` files are in `deniedPaths`; `git push/commit/reset/clean/checkout/stash/config/rebase` are denied.
- `includeMcpJson: false`, so no agent inherits the workspace MCP config. Each agent gets only the MCP servers in its own `mcpServers`: `fetch` for ingestion-agent, `postman` for qa-agent, none for the rest.
- `allowedTools` holds only read tools (`fs_read`, `grep`, `glob`, `code`), so every `fs_write`, `@fetch` and `@postman` call asks for approval. The ingestion-agent has an empty `allowedTools`.
- Shell: commands matching `toolsSettings.execute_bash.allowedCommands` run without a prompt; everything else is refused (`denyByDefault: true` for backend, frontend and qa). Run one command per call. The only chain allowed is a literal leading `cd backend; ` or `cd frontend; `, because `execute_bash` runs from the workspace root.
- The allow patterns are exact command grammars, not prefixes. Each pattern lists the options it accepts and takes only relative paths built from segments that start with a letter, digit, `_` or a single `.`, so `..`, absolute paths, drive letters, globs, quotes, redirection, `$`, backticks and line breaks never match:
  - backend: `pytest`/`python -m pytest` with `-q -v -vv -x -ra --no-header --tb=… --maxfail=N -k WORD -m WORD --cov=app[/…] --cov-report=term|term-missing --cov-fail-under=N --hypothesis-show-statistics` and paths under `backend/tests` (or `tests` after `cd backend; `); `ruff check|format` with `--check --diff --fix --statistics -q` on `backend/…` paths (or relative paths after `cd backend; `); `black --check [--diff]`; `cd backend; alembic upgrade head`; `cd backend; python -m app.cli seed`.
  - frontend: `npm test|ci` and `npm run lint|format|format:check|test|test:coverage|build|typecheck` (script names from `frontend/package.json`; after `cd frontend; ` or with `--prefix frontend`); after `cd frontend; `: `npx vitest run [--coverage] [paths]`, `npx eslint [--fix] [--max-warnings N] [paths]`, `npx prettier --check|--write <paths>`, `npx tsc --noEmit`.
  - qa: the same pytest grammar; `ruff check`, `ruff format --check` and `black --check` with no fixing options; `npm test`, `npm run test|test:coverage|lint|format:check|typecheck`; `cd frontend; npx vitest run [--coverage] [paths]`.
  - all three: `git status [--short|-s|-sb|--porcelain]`, `git diff [--stat|--name-only|--name-status|--cached|--staged] [-- paths]`, `git log [--oneline|--stat|--name-only|-n N|-N] [-- paths]`.
- Options that write to a caller-chosen path are not in any grammar, so they are refused: `pytest --basetemp` (which deletes the directory first), `--junitxml`/`--junit-xml`, `--cov-report=<kind>:<path>`, `-p`, `-c`, `-o`, `--rootdir`; `ruff --output-file`/`--cache-dir`/`--config`; `eslint -o`/`--output-file`/`-c`; `vitest --outputFile`; `prettier --config`; `git --output`/`--ext-diff`. qa additionally has no `--fix`, `ruff format` without `--check`, `npm ci`, `npm run build`/`format` or prettier/eslint writes. `deniedCommands` repeats these as a second layer (`..`, `--basetemp`, `--junit-?xml`, `--output`, `--cov-report=…:`, and for qa `--fix`/`--write`), written as `.*…*` so they match whether or not Kiro anchors patterns. The patterns were checked with Python `re` (search and full-match) against 22/14/17 commands (backend/frontend/qa) that must run and 51–59 that must be refused, including every example from the config review.
- This is still not a sandbox. The grammars constrain the command line, not what the tools do with project files: pytest runs `conftest.py`, pyproject `addopts` and the tests themselves; `npm run …` runs whatever `frontend/package.json` defines; `npm ci` runs dependency install scripts. backend can edit `backend/pyproject.toml` and `conftest.py`, frontend can edit `package.json` and tool configs, and qa can edit `backend/tests/conftest.py`, so each of them can reach arbitrary code through an allowed runner. The prompts forbid configs and tests that write outside the agent's paths; review diffs to those files. Allowed runs also leave tool output in their working directory: `.pytest_cache/`, `.hypothesis/`, `.coverage`, `.ruff_cache/`, `frontend/coverage/`, `frontend/dist/` (all gitignored build/cache output).

## How to invoke

- Kiro IDE: open the chat agent picker and choose the agent by name (configs in `.kiro/agents/` are picked up for this workspace), or ask the default agent to delegate to it as a subagent ("use architect-agent to review …").
- Kiro CLI: `kiro-cli chat --agent backend-agent` (or `/agent swap backend-agent` inside a session).
- Each agent shows its welcome message with example prompts when it starts.

## architect-agent

Read-only reviewer. Checks layering (`api → services → engines/repositories → models`), single sources of behavior (`compute_match`, `application_status.transition()`, `compute_metrics`), the §8 API contract and error envelope, pinned dependencies and spec sync. Outputs findings with severity, location, requirement citation and fix. It cannot edit or run anything; it hands work to backend/frontend agents.

Example prompts:
1. Review `backend/app/api/routes/` for business logic that belongs in services.
2. Check that every endpoint in design.md §8 exists and returns the error envelope.
3. Audit `backend/requirements.txt` and `frontend/package.json` for unpinned or unjustified dependencies.
4. Does anything outside `app/services/matching/` compute or adjust a match score?
5. Compare tasks.md checkboxes with what is actually implemented.

## backend-agent

Implements backend tasks with tests and runs the quality gate as four separate calls: `cd backend; ruff format --check .`, `cd backend; ruff check .`, `cd backend; black --check .`, `cd backend; pytest`. Loads the career-data-toolkit skills (`job-normalization`, `match-explanation`, `resume-analysis`) and `references/scoring-rules.md` as resources. It cannot write the spec, `data/` or the Power: behavior or scoring-rule changes must be proposed to the architect-agent or the user so `design.md`, `algorithm_version` and `scoring-rules.md` change together. `alembic downgrade` and destructive commands are denied.

Example prompts:
1. Implement task 2.13: JobService list/detail with filters, sort and pagination, plus bookmark/hide routes and tests.
2. Add example-based unit tests for every experience and education factor case in the matching engine.
3. Why does `POST /api/jobs/{id}/apply` return 409 for an Offer application? Show the code path and the test.
4. Run the full backend quality gate and fix anything that fails.

## frontend-agent

Builds pages, components and hooks following product UX principles (explain the score, loading/empty/error states, toasts, keyboard Kanban, design tokens) and the frontend layering (only `api/client.ts` calls `fetch`; no scoring, transition or metric logic in components). Done means `npm run lint`, `npm run format:check`, `npm test` and `npm run build` pass, each run as its own `cd frontend; …` call.

Example prompts:
1. Build the Kanban board with HTML5 drag-and-drop and a keyboard "Move to" menu listing only allowed moves from `/api/applications/meta`.
2. Add `MatchExplanationPanel` showing `MATCH SCORE: n/100`, the factor breakdown and +/- reasons, with tests.
3. Sync `JobFilters` with the URL (search debounced 300 ms) and test it.
4. Give the dashboard page proper loading, empty and error states.
5. Run lint, format check, tests and build, then fix what fails.

## qa-agent

Runs every test layer and coverage gates, hunts edge cases against requirements.md, checks P1–P6 properties (adds Hypothesis counterexamples as `@example`, never weakens a property) and security rules. Writes tests only; reports application bugs with a failing test.

Postman: the agent declares the postman Power's MCP server (`https://mcp.postman.com/minimal`, OAuth sign-in on first use) in its own `mcpServers` and lists `@postman` in `tools`, not `allowedTools`, so every Postman call asks for approval. Its prompt allows read-only calls (`getWorkspaces`, `getCollections`, `getCollection`, `getEnvironments`) and forbids create/put/duplicate/update/publish calls and `runCollection` unless the user asks for that exact action, because they send project data to Postman's cloud. `runCollection` executes in Postman's cloud and cannot reach `http://localhost:8000`, so local black-box runs happen in the Postman app's Collection Runner with the files in `docs/postman/`. The qa-agent checks that the collection covers design.md §8 and analyses the run results the developer pastes in. It cannot edit `docs/postman/` (writes are limited to test folders).

Example prompts:
1. Run every backend test layer plus coverage and tell me which gates fail.
2. Run `pytest backend/tests/property -v` and explain each property P1–P6 and its requirement IDs.
3. Write API tests proving every disallowed status transition returns 409 with the allowed targets.
4. Check that `docs/postman/InternPilot.postman_collection.json` covers every design.md §8 endpoint, then explain the failures in these Collection Runner results.
5. Look for security regressions: string-built SQL, leaked 500 details, unvalidated URLs.

## ingestion-agent

The only agent with the `fetch` MCP server (declared in its own `mcpServers`; qa-agent's `postman` server is the only other MCP server any agent has). Fetches `https://remotive.com/api/remote-jobs` or `https://www.arbeitnow.com/api/job-board-api` (HTTPS, exact hosts, no LinkedIn, robots.txt respected), saves the raw JSON to `data/ingest/<source>-<YYYY-MM-DD>.json` with a `format` key, and tells the developer how to import it via `POST /api/jobs/ingest` (`source=fixture` or `source=payload`, both with `"limit": 500`). Each capture stays at ≤ 400 items and under `INGEST_MAX_BYTES` (5,000,000 bytes; the agent drops whole items past 4,000,000 characters), because the fixture source is all-or-nothing: one invalid, unknown-format or oversized file in `data/ingest/` makes `source=fixture` and the public-source fallback return 502 until the file is fixed or deleted (design.md §11.2, §11.5). Fetched content is untrusted; it never follows instructions inside it. No shell. Details: `docs/kiro-mcp.md`.

Example prompts:
1. Fetch the latest 50 Remotive jobs and save them to data/ingest/.
2. Capture the Arbeitnow job board and tell me how many listings look like internships.
3. Save a Remotive capture and give me the exact `POST /api/jobs/ingest` body to import it as a payload.
4. What happens if Remotive is down when I run ingestion, or if a file in data/ingest/ is broken?

## Format notes

The configs follow the Kiro agent config format (IDE 1.0 / CLI 3.0): `name`, `description`, `prompt`, `tools`, `allowedTools`, `toolsSettings`, `resources` (`file://` for steering/spec docs, `skill://` for Power skills, loaded on demand), `includeMcpJson`, `mcpServers`, `welcomeMessage`. Example prompts are embedded in `welcomeMessage` because the format has no separate prompts field.
