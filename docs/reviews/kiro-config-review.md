# Kiro MCP, Powers and custom agents for InternPilot AI (Phase 7: 7.1, 7.3, 7.4, 7.5), pass 3

This pass checks the fixes for the four pass-2 findings. Findings 2, 3 and 4 are fixed. The shell allow-lists in backend, frontend and qa are now exact command grammars. Every pass-2 example (`--basetemp`, `--junitxml`, `ruff format ../data`, `prettier --write ../…`, `eslint --fix ../…`, `git diff --output`) is outside the grammars and also caught by `deniedCommands`. kiro-mcp.md and the ingestion-agent prompt now describe fixture ingestion as all-or-nothing, matching design.md §11.2/§11.5 and `FixtureSource`. Import bodies use `"limit": 500`. The cheap gates pass again: all nine JSON deliverables parse, `.kiro/mcp.json` equals the required object, and the §5.3, §5.4 and §5.5 bodies of design.md are exact substrings of `scoring-rules.md`. One blocking item is left, and it is not something the implementer can fix.

Watch for: `.kiro/settings/mcp.json` still does not exist (confirmed). A kiro-scope rule blocks automated writes to `.kiro/settings/`, so the user or orchestrator has to create it. Until then 7.1 does not meet the brief's "both files" requirement. The ingestion-agent's "4,000,000 characters" rule does not guarantee a file under 5,000,000 bytes (confirmed arithmetic, low practical risk).

**Verdict**: NEEDS_CHANGES

## High-level view

Agent wiring matches the role table. Only ingestion has `fetch` and only qa has `postman`. architect is read-only. backend, frontend and qa use `denyByDefault` with exact grammars: relative path segments only, no `..`, no output-file options, and no chains apart from a literal leading `cd backend; ` or `cd frontend; `. qa's grammar is check-only. The docs now present this as a command-line limit, not a sandbox, and name `conftest.py`, `addopts`, `package.json` scripts and `npm ci` install scripts as the remaining routes. Two points are still untested: whether Kiro checks `deniedCommands` before `allowedCommands`, and whether it anchors patterns (possible). The `^…$` grammars and the `.*…*` deny patterns hold either way.

The ingestion docs agree with the spec. kiro-mcp.md lists the fixture failure reasons as `invalid_json`, `unexpected_shape`, `too_large` and `read_error`, which match the tokens in `sources.py`. It also covers the 502 on both `source=fixture` and the public-source fallback, and gives recovery steps. The byte-cap heuristic has a small gap: 4,000,000 characters of non-ASCII UTF-8 can take more than 5,000,000 bytes.

The working tree still holds the parallel run's changes (`backend/**`, `frontend/**`, `data/**`, design.md, tasks.md, `.env.example`, `docker-compose.yml`, `.gitattributes`, `.gitkeep` deletions). None of them come from this deliverable set, so the Phase 7 commit must stage its own paths by name.

<details>
<summary>Issues (3)</summary>

1. **Live MCP config still missing** (blocking, confirmed; user/orchestrator action): `.kiro/settings/` has only `.gitkeep`. Create `.kiro/settings/mcp.json` with the exact object in `.kiro/mcp.json` (kiro-mcp.md Setup steps 2–4), confirm `fetch` connects, and replace the "Open item" paragraph in kiro-mcp.md Verification with that result.
2. **Character cap does not bound bytes** (non-blocking, confirmed): 4,000,000 characters can exceed 5,000,000 bytes once more than about a quarter of the bytes are multi-byte. In the ingestion-agent prompt, tell the agent to write non-ASCII characters as `\uXXXX` escapes, so characters equal bytes, or lower the cap. Then drop the "leaving room for multi-byte UTF-8" claim in kiro-mcp.md.
3. **Ingestion example prompt drift** (non-blocking, confirmed): example prompt 4 in `ingestion-agent.json` asks about a broken `data/ingest/` file, but the copy in kiro-agents.md does not. Make the two match.

</details>

<details>
<summary>Details</summary>

### Live config under `.kiro/settings/`

The brief and tasks.md 7.1 require both files. kiro-mcp.md no longer claims the live file exists. It stays blocking because the deliverable is incomplete, but another implementer pass cannot fix it, since the implementer reports three writes denied by a kiro-scope rule. The fix is one paste through "Open Workspace MCP Config".

### Capture size cap

The ingestion-agent prompt says to keep the saved JSON text under 4,000,000 characters, and kiro-mcp.md calls the margin "room for multi-byte UTF-8". `FixtureSource` compares `path.stat().st_size`, in bytes, against `INGEST_MAX_BYTES`. A character in the Basic Multilingual Plane takes up to 3 bytes, so text where more than about 25% of the bytes come from multi-byte characters can pass the character check and still produce a `too_large` file. That file would then take down the whole fixture source. Arbeitnow listings are mostly German and English, so in practice the risk is low. The fix is still simple: write the file with non-ASCII escaped. JSON allows this, and the item data stays the same.

</details>

<details>
<summary>File map</summary>

- `.kiro/mcp.json`: fetch server definition, exact required object.
- `.kiro/settings/mcp.json`: missing (Setup steps in kiro-mcp.md).
- `docs/kiro-mcp.md`: failure handling rewritten for all-or-nothing fixtures, `limit` 500, a Limits section, the open item updated.
- `docs/postman/InternPilot.postman_collection.json`: "Ingest - fixtures" body uses `limit` 500, and its description covers the 502.
- `docs/postman/InternPilot.postman_environment.json`: unchanged (`baseUrl`, `demoUser`).
- `docs/kiro-powers.md`: side-effects bullet covers the fixture 502.
- `.kiro/powers/career-data-toolkit/`: unchanged. `scoring-rules.md` still contains design.md §5.3–5.5 verbatim.
- `.kiro/agents/{backend,frontend,qa}-agent.json`: exact command grammars plus a `deniedCommands` second layer.
- `.kiro/agents/ingestion-agent.json`: 400-item and byte caps, all-or-nothing explanation, `limit` 500 next steps.
- `docs/kiro-agents.md`: grammar list, refused options, not-a-sandbox caveat.

Full diff: Phase 7 files are untracked; read them directly (`git status --short`).

</details>
