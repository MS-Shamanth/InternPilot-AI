# Kiro challenge evidence

| Lesson | Evidence | Notes |
|---|---|---|
| Specs | `.kiro/specs/internship-intelligence/{requirements,design,tasks}.md` | EARS requirements R1–R15 + NFRs, design with properties P1–P6, all tasks ticked. Review rounds in `docs/reviews/`. |
| Steering | `.kiro/steering/{product,architecture,coding-standards,testing,security}.md` | Applied to every task. |
| Hooks | `.kiro/hooks/{python-format,ts-format,backend-tests,task-tests}.json` | Triggers, matchers and loop avoidance in [kiro-workflow.md](kiro-workflow.md). |
| MCP | `.kiro/settings/mcp.json`, `.kiro/mcp.json` (`fetch` server) | Fetch → `data/ingest/*.json` → `POST /api/jobs/ingest`; see [kiro-mcp.md](kiro-mcp.md). |
| Powers | Postman collection + environment in `docs/postman/`; custom Power `.kiro/powers/career-data-toolkit/` | See [kiro-powers.md](kiro-powers.md). |
| Custom agents | `.kiro/agents/{architect,backend,frontend,qa,ingestion}-agent.json` | Role-restricted tools; see [kiro-agents.md](kiro-agents.md). |
| Property-based testing | `backend/tests/property/` (Hypothesis P1–P6) | Properties ↔ requirements in [testing.md](testing.md). |
| Bonus 2: Package a Kiro power | `.kiro/powers/career-data-toolkit/` (`POWER.md` frontmatter, `plugin.json`, three skills, `references/scoring-rules.md`) | Shareable as a public GitHub repo; install steps in [kiro-powers.md](kiro-powers.md). |
| Bonus 1: Kiro Web / cloud sessions | Not used | Intentionally skipped for this submission. |

## Final audit (task 8.4)

Run locally on Windows (Python 3.12.7, Node 22.19.0, npm 10.9.3). No fixes were needed.

| Check | Command | Result |
|---|---|---|
| Backend tests, all layers | `pytest --cov=app --cov-report=term-missing` | 1712 passed |
| Property tests | `pytest tests/property -v` | 10 passed (P1–P6 + normalization idempotence) |
| Backend coverage | same run | 99% overall; `app/services/matching/` 98–100% per file (gates: 80% / 95%) |
| Backend lint/format | `ruff check .`, `ruff format --check .`, `black --check .` | Clean |
| Frontend tests + coverage | `npm run test:coverage` | 35 files, 318 tests passed; all files 95.7% lines, `src/lib` 97.7%, every `src/components/*` folder ≥ 87% (gate: 60%) |
| Frontend lint/format/build | `npm run lint`, `npm run format:check`, `npm run build` (`tsc --noEmit` + Vite) | All exit 0 |
| Secrets | `git check-ignore`, `git ls-files --cached --others --exclude-standard`, pattern scan (cloud/API keys, private keys, JWTs, credentialed DB URLs) | `.env`/`*.env` ignored and untracked; only placeholder or test-canary values found; `.env.example` uses `change-me`; compose takes credentials from `.env` |
| Tracked artifacts | same file list | No `node_modules`, virtualenvs, `dist`, `.coverage`, `.hypothesis`, DB files or dumps |
| Code hygiene | grep | No `TODO`/`FIXME`; no `print(` in `backend/app`; no `dangerouslySetInnerHTML`; `fetch` only in `src/api/client.ts`; wall-clock reads only in `core/clock.py` |
| Task list and artifacts | `tasks.md` 1.1–8.3, file existence + JSON parse | All ticked; docs, hooks, agents, MCP configs, Power and Postman files present and valid |
| `docker compose up` | not re-run in this audit | Previously verified in task 8.1; see [demo.md](demo.md) |
