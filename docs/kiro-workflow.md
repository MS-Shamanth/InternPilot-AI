# Kiro workflow: hooks

Hooks live in `.kiro/hooks/*.json` (format `{"version": "v1", "hooks": [{name, trigger, matcher, action}]}`). Every action is a `command` that `cd`s into `backend/` or `frontend/` and calls the project-local tools (`backend/.venv/Scripts/*.exe`, `frontend/node_modules/.bin/*.cmd`), so no global installs are needed. Commands use `cmd /c` because the dev machine is Windows.

| File | Trigger | Matcher (path regex) | Action | Timeout |
|---|---|---|---|---|
| `python-format.json` | `PostFileSave` | `backend/(app\|tests\|alembic)/**.py` | `ruff check --fix --exit-zero` then `ruff format` on `app tests alembic` | 60 s |
| `ts-format.json` | `PostFileSave` | `frontend/src/**.{ts,tsx}` | `eslint --fix --quiet src` then `prettier --write src` | 90 s |
| `backend-tests.json` | `PostFileSave` | `backend/app/**.py` | `pytest tests/unit -q -x -p no:cacheprovider` | 120 s |
| `task-tests.json` | `PostTaskExec` | none | full `pytest -q -p no:cacheprovider`, then `npm test` in `frontend/` | 600 s |

## Rationale

- Format hooks keep `ruff format`/`ruff check` and Prettier/ESLint clean without anyone remembering to run them (steering: coding-standards). They cover the whole source tree, not only the saved file, so a hook never leaves a half-formatted tree.
- Lint fixers run before formatters, so the formatter always has the last word and the result matches CI's `ruff format --check` / `prettier --check`.
- `ruff check` uses `--exit-zero`: unfixable findings are reported, not treated as a hook failure. CI still enforces them.
- The save-time test hook runs only the fast unit suite (no DB, no network). The full backend and frontend suites run once per finished spec task, which is the "done" gate from the testing steering file.

## Loop avoidance

- Idempotent: ruff, ESLint `--fix` and Prettier converge. A second run on already-clean files writes nothing, so it cannot cause another change.
- The tools write files directly on disk. They do not go through an editor save, so they do not fire `PostFileSave` again. Even if a save were fired, the next pass would be a no-op.
- The test hooks are read-only. They pass no fix flags and `-p no:cacheprovider` disables pytest's cache. Vitest writes nothing under `src/`. No test hook matches the files it could touch.
- The matchers exclude `.venv`, `node_modules`, caches and build output, so tool artifacts never trigger a hook.
