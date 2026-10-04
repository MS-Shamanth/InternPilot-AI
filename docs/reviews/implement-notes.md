# Implement notes: Phase 7 Kiro config (tasks 7.1, 7.3, 7.4, 7.5)

## Follow-up after review pass 3

| # | Finding | Fix |
|---|---|---|
| 1 | `.kiro/settings/mcp.json` missing | Created by the developer. Checked: parses, equals the required object. `.kiro/mcp.json` had gone missing from disk in the meantime and was recreated with the same object (also checked equal). kiro-mcp.md Verification open item replaced with this result; MCP panel connection is per the developer's report, not agent-verified. |
| 2 | 4,000,000-char cap does not bound bytes | ingestion-agent prompt: write ASCII-only JSON with `\uXXXX` escapes, so characters = bytes; kiro-mcp.md Limits bullet corrected. |
| 3 | Example prompt 4 out of sync | kiro-agents.md now matches the welcome message exactly. |

Checks: both MCP files == required object (True, True); ingestion-agent.json parses; prompt 4 text present in kiro-agents.md.

## Iteration 3 (fixes for review pass 2)

| # | Finding | Fix |
|---|---|---|
| 1 | `.kiro/settings/mcp.json` missing | Write attempted a third time with the exact object; denied again (`Rule: deny fs_write matching ".kiro/settings/ ..." Source: kiro-scope`). Not bypassed via shell. Still needs the user/orchestrator (Setup steps 2–4 in `docs/kiro-mcp.md`); the Verification open item now says "attempted in all three config iterations". |
| 2 | Tool options write outside `fs_write` paths | backend/frontend/qa `allowedCommands` replaced by exact command grammars: each pattern enumerates its accepted options and accepts only relative paths made of segments `\.?\w[\w.-]*` (no `..`, no absolute/drive paths, no globs or quotes). `--basetemp`, `--junitxml`, `--cov-report=<kind>:<path>`, `-p/-c/-o/--rootdir`, ruff `--output-file/--cache-dir/--config`, eslint `-o`, vitest `--outputFile`, prettier `--config`, `git --output/--ext-diff` match no grammar. qa has no `--fix`, no `ruff format` without `--check`, no `npm ci/build/format`, no prettier/eslint writes. Root-relative ruff/black need `backend/...` paths; the only chain is a literal leading `cd backend; ` / `cd frontend; ` (execute_bash runs at the workspace root, so the old `a ; b ; c` quality-gate lines, which the old patterns refused anyway, are now one call per command in both prompts and docs). `deniedCommands` adds a second layer written as `.*X.*` (`..`, `--basetemp`, `--junit-?xml`, `--output`, `--cov-report=\S*:`, qa `--fix/--write`). No lookarounds, so the patterns work in Rust `regex` as well as JS/Python. npm script names aligned with the now-existing `frontend/package.json` (`test:coverage`, not `coverage`). `kiro-agents.md`: closed-routes claim replaced with the grammar list, the refused options, and a not-a-sandbox caveat naming `conftest.py`, pyproject `addopts`, `package.json` scripts and `npm ci` install scripts plus the cache/output dirs runs leave behind (all gitignored, checked in `.gitignore`). Prompts forbid configs/tests that write outside the agent's paths. |
| 3 | Fixture failure handling contradicts §11.2 | `kiro-mcp.md` Failure handling rewritten: fixture files are all-or-nothing; invalid JSON / unknown `format` / other shape / > 5,000,000 bytes / unreadable → `source=fixture` 502 `INGESTION_SOURCE_UNAVAILABLE`, and the remotive/arbeitnow fallback 502s too; recovery = read `details.reason`, fix or delete the file, retry. "Valid items still import" now applies only within a valid file/payload. `ingestion-agent.json` prompt: ≤ 400 items, saved text ≤ 4,000,000 characters (drop whole items, or lower Remotive `limit`) so the file stays under `INGEST_MAX_BYTES`; save nothing on parse failure; explains the 502 and recovery. Welcome message mentions the caps. `kiro-powers.md` side-effects bullet and the collection's "Ingest - fixtures" description note the 502. Checked against `FixtureSource`/`PayloadSource` in `backend/app/services/ingestion/sources.py` (read-only) and confirmed `SeedService` reads `seed_jobs.json` directly, so seeding is unaffected. |
| 4 | Fixture `limit` truncates captures | `"limit": 500` in kiro-mcp.md 3a/3b, the ingestion-agent next-step bodies, and the Postman "Ingest - fixtures" body (was 100). kiro-mcp.md "Limits" explains the cap counts across files with `seed_jobs.json` (32 items) first, hence the 400-item capture cap; larger captures go through `source=payload` one at a time (payload also applies `limit`). |

### Verification run (iteration 3)

| Check | Command / method | Result |
|---|---|---|
| JSON parses | `json.loads` on all 9 JSON deliverables | all PARSE OK (`.kiro/mcp.json`, collection, environment, `plugin.json`, 5 agents) |
| MCP content exact | parsed `.kiro/mcp.json` == required object | True; `.kiro/settings/mcp.json` exists: False (finding 1) |
| Shell grammars | Python `re`, both `search` and `fullmatch`, allow-list minus deny-list, patterns loaded from the agent files and asserted equal to the tested set | must-run: backend 22, frontend 14, qa 17 all run; must-refuse: 51 common (every reviewer example incl. `pytest --basetemp=.kiro/steering`, `--junitxml=…`, `ruff format ../data`, `npx prettier --write ../.kiro/steering`, `npx eslint --fix ../backend`, `git diff --output=…`, plus `..` inside paths, absolute paths, `-p/-c/-o`, redirection, `$()`, backticks, newlines, `;`/`&&` chains) + 8 qa-only (`ruff check --fix`, `ruff format backend`, `npm ci`, `npm run build/format`, prettier `--write`, eslint `--fix`) all refused; deny list alone also catches the reviewer examples. ALL OK |
| Agent wiring | parsed `tools`/`mcpServers` | architect read-only, no MCP; backend/frontend none; qa `@postman` + `postman`; ingestion `@fetch` + `fetch` only |
| Scoring rules match | design.md §5.3, §5.4, §5.5 bodies exact substrings of `scoring-rules.md` | True, True, True (unchanged) |
| Secrets | regex `(api_key|secret|token|password|bearer)[:=]"<6+ chars>"` over all 18 deliverables | none |
| Git scope | `git status --short` (read-only) | Phase 7 paths untracked as before; everything else (`.env.example`, design.md, tasks.md, tasks.meta.json, `backend/**`, `frontend/**`, `data/**`, `docker-compose.yml`, `.gitattributes`, `.gitkeep` deletions) is the parallel run's. Stage Phase 7 paths by name. |

Helper scripts lived in `%TEMP%` (outside the repo) and were deleted afterwards. Not verified: how Kiro evaluates `allowedCommands`/`deniedCommands` at runtime (anchoring, precedence); the grammars are written to be safe either way.

## Iteration 2 (fixes for `kiro-config-review.json`)

| # | Finding | Fix |
|---|---|---|
| 1 | qa-agent has no Postman Power access | `qa-agent.json`: `@postman` added to `tools` (not `allowedTools`, so every call asks); `mcpServers.postman = {"url": "https://mcp.postman.com/minimal", "disabled": false}`, copied from the installed Power's `mcp.json`. Prompt allows read-only `get*` calls and forbids create/put/duplicate/update/publish/`runCollection` unless the user asks for that exact action. `runCollection` runs in Postman's cloud and cannot reach localhost, so local runs are in the Postman app's Collection Runner and qa analyses the results. Example prompt 4 and the welcome message rewritten to match. `kiro-agents.md` and `kiro-powers.md` updated the same way. |
| 2 | Shell allow-list regexes bypass `fs_write` limits | Every `allowedCommands` pattern in backend (7), frontend (4) and qa (8) now ends in `[^&;|<>$`\r\n]*$` (JSON-escaped `\\r\\n`). |
| 3 | `.kiro/settings/mcp.json` missing | Write attempted again and denied: `Rule: deny fs_write matching ".kiro/settings/ ..." Source: kiro-scope`. Not bypassed via shell. Still needs the orchestrator or user (Setup steps in `docs/kiro-mcp.md`). `kiro-mcp.md` Config row and Verification now say the file is an open item instead of describing it as existing. |
| 4 | "Shell always asks for approval" inaccurate | `kiro-agents.md` common rules rewritten: lists the commands that auto-run per agent, says everything else is refused, and states the allow-list character class and that it is not a sandbox. |
| 5 | frontend shell not `denyByDefault` | `frontend-agent.json` `denyByDefault: true`; prompt and docs table say other commands are refused. |
| 6 | Collection "leaves demo data as it found it" overclaims | `kiro-powers.md`: claim removed; new "Side effects of a full run" section (payload job `Example Labs`/`900001`, fixture re-import + `jobs_ingested`, live imports when online / Arbeitnow 502 offline, bookmark/hide events, `profile_updated` and the standalone Replace-profile overwrite). Reset = `docker compose down -v`, because seed never overwrites an existing demo user (design.md §12). |
| 7 | Out-of-scope paths changed | Not caused by this step (parallel run). No edits outside the deliverables; orchestrator should stage Phase 7 paths by name. |

Also: `kiro-powers.md` "Activation status and tools" now lists the 40 minimal-mode tools from the installed Power's `POWER.md` (no `kiro_powers` tool in this session, no sign-in, nothing uploaded), and explains why the Power's suggested `fileEdited` hook was not created.

Incident during this iteration: `str_replace` treated `` $` `` in the new regex as a substitution token and corrupted the three agent files. All three were rewritten in full and re-checked (one `"name"` key each, parse OK, content diffed by eye against iteration 1 plus the intended changes).

### Verification run (iteration 2)

| Check | Command / method | Result |
|---|---|---|
| JSON parses | `json.load` on all 9 JSON deliverables | all OK: `.kiro/mcp.json`, collection, environment, `plugin.json`, 5 agents |
| MCP content exact | parsed `.kiro/mcp.json` == required object | True; `.kiro/settings/mcp.json` exists: False (blocked, finding 3) |
| Regex hardening | Python `re` on each agent's `allowedCommands` against `git log > .kiro/steering/security.md`, `pytest $(Set-Content x y)`, ``pytest `whoami` ``, `pytest -q\nSet-Content x y`, `pytest < in.txt`, `npm test ; rm x` | 0 matches for all agents |
| Regex still allows intended commands | `pytest backend/tests/unit -q`, `ruff check .`, `python -m app.cli seed`, `git status --short`, `npm test`, `npm run build`, `npx vitest run`, `pytest --cov=app --cov-report=term-missing`, `git diff`, `npm run coverage` | all matched by the right agent |
| Agent wiring | parsed `tools` / `mcpServers` / `denyByDefault` | architect read-only, no MCP; backend/frontend/qa `denyByDefault: true`; qa `@postman` + `mcpServers.postman`; ingestion `@fetch` + `mcpServers.fetch` (only `fetch`) |
| Scoring rules match | design.md §5.3, §5.4, §5.5 bodies are exact substrings of `scoring-rules.md` | True, True, True (scoring-rules.md unchanged this iteration) |
| Secrets | regex `(api_key|secret|token|password|bearer)\s*[:=]\s*"<6+ chars>"` over all deliverables | no hits |
| Git scope | `git status --short` (read-only) | changes outside deliverables are only the parallel run's (`backend/**`, `design.md`, `tasks.md`, `tasks.meta.json`); untracked `docs/reviews/*` review files are the reviewer's |

Not verified: Kiro loading the agents and the remote `postman` server in a custom agent (needs the IDE and OAuth sign-in); `runCollection` reachability of localhost is inferred from it running in Postman's cloud, not tested; the collection against a live server (endpoints still being built); task 7.2 (deferred).

## Iteration 1

### Files created

- 7.1: `.kiro/mcp.json`, `docs/kiro-mcp.md`
- 7.3: `docs/postman/InternPilot.postman_collection.json`, `docs/postman/InternPilot.postman_environment.json`, `docs/kiro-powers.md`
- 7.4: `.kiro/powers/career-data-toolkit/{plugin.json, POWER.md, README.md, references/scoring-rules.md, skills/{job-normalization,resume-analysis,match-explanation}/SKILL.md}`
- 7.5: `.kiro/agents/{architect,backend,frontend,qa,ingestion}-agent.json`, `docs/kiro-agents.md`

### Deviations (approved by orchestrator)

- `.kiro/settings/mcp.json` NOT created: the path is protected by a kiro-scope permission rule. `docs/kiro-mcp.md` has Setup steps.
- `backend-agent.json` scoped to `backend/**` with a `denyByDefault` shell allow-list; spec/scoring-rule changes are proposed to architect/user.
- `postman` Power not activated (no `kiro_powers` tool); nothing uploaded.

### Format decisions

- Agents follow the Kiro agent config (IDE 1.0 / CLI 3.0): `name, description, prompt, tools, allowedTools, toolsSettings, resources (file:// and skill://), includeMcpJson, mcpServers, welcomeMessage`. Example prompts are inside `welcomeMessage`.
- `plugin.json` follows Agent Plugins 1.0.0; Kiro fields sit under `extensions["dev.kiro"]`. A legacy `POWER.md` is included as well.
- `scoring-rules.md` is design.md §5 (5.1–5.6) copied programmatically with headings demoted one level, plus a weight table header.

### Verification (iteration 1)

- `uvx --version` → `uvx 0.11.3 (45da18ac3 2026-04-01 x86_64-pc-windows-msvc)`.
- Collection covers all 21 design.md §8 routes (0 missing).
- `normalize_skill`/`display_skill` examples in the job-normalization skill match `backend/app/services/matching/normalization.py`.
