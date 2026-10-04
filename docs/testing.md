# Testing

All commands run from the named directory. No test touches the network; time comes from an injected `FixedClock`.

## Backend (`backend/`)

| Layer | Command |
|---|---|
| Unit | `pytest tests/unit` |
| Integration (repositories, services, DB constraints) | `pytest tests/integration` |
| API (FastAPI `TestClient`) | `pytest tests/api` |
| Property-based (Hypothesis) | `pytest tests/property -v` |
| Everything + coverage | `pytest --cov=app --cov-report=term-missing` |
| Lint / format | `ruff check .`, `ruff format --check .`, `black --check .` |

`tests/conftest.py` sets `DATABASE_URL` before importing the app: `TEST_DATABASE_URL` if set, otherwise in-memory SQLite. It also registers and loads the Hypothesis profile `internpilot` (`max_examples=200`, `derandomize=True`, `deadline=None`). Shared strategies live in `tests/property/strategies.py`. The service-level state machine for P6 runs 50 examples of up to 20 steps, because each example builds a fresh SQLite schema.

### Running against PostgreSQL

```powershell
docker run -d --rm --name internpilot-pgtest -e POSTGRES_USER=internpilot `
  -e POSTGRES_PASSWORD=<random> -e POSTGRES_DB=internpilot_test `
  -p 127.0.0.1:55433:5432 postgres:16-alpine
$env:TEST_DATABASE_URL = "postgresql+psycopg://internpilot:<random>@127.0.0.1:55433/internpilot_test"
pytest tests/integration tests/api
docker rm -f internpilot-pgtest
```

Generate the password when you run it. Don't commit it.

**Recorded result (NFR2):** `pytest tests/integration tests/api` on `postgres:16-alpine` (Docker 29.3.1, loopback port 55433, throwaway container with a password generated at runtime): **336 passed**, 0 failed, 0 skipped.

## Frontend (`frontend/`)

| What | Command |
|---|---|
| Component/interaction tests (Vitest + Testing Library) | `npm test` |
| Coverage (gate: 60% lines for `src/components`, `src/lib`) | `npm run test:coverage` |
| Lint | `npm run lint` |

Tests mock at the `src/api/*` boundary, and `tests/setup.ts` stubs `fetch`. Coverage instrumentation slows the run, so on a loaded machine add `-- --testTimeout=30000`.

## Coverage gates

| Scope | Gate | Last measured |
|---|---|---|
| Backend `app/` (lines) | ≥ 80% | 99% |
| `app/services/matching/` | ≥ 95% | 98–100% per module |
| Frontend `src/components` + `src/lib` (lines) | ≥ 60% | 95.7% |

## Properties ↔ requirements (design.md §17)

| Property | Test | File | Requirements |
|---|---|---|---|
| P1 Score bounds | `test_p1_score_is_bounded` | `test_matching_properties.py` | R3.1, R3.3, R3.4, R4.1, R4.2 |
| P2 Monotonicity | `test_p2_adding_matching_skill_never_lowers_score`, `test_p2_adding_unrelated_skill_changes_nothing` | `test_matching_properties.py` | R3.5, R3.6 |
| P3 Duplicates | `test_p3_duplicate_skills_have_no_impact` | `test_matching_properties.py` | R3.2, R3.7 |
| P4 Missing skills | `test_p4_missing_required_skills_get_no_credit` | `test_matching_properties.py` | R3.8, R3.9, R4.3 |
| P5 Determinism | `test_p5_match_is_deterministic_and_order_independent` | `test_matching_properties.py` | R3.10, R3.11, R4.6 |
| P6 Status validity | `test_p6_application_always_has_one_valid_status` (pure), `test_p6_application_always_has_one_valid_status_in_service` (`RuleBasedStateMachine` over `ApplicationService` on SQLite) | `test_application_status_properties.py` | R5.2, R5.4, R5.5 |
| Normalization idempotence | `test_p_normalize_skill_is_idempotent_*` | `test_normalization_properties.py` | R1.3, R3.2 |

If Hypothesis finds a counterexample, add it as an `@example(...)` and fix the code. Don't weaken the property.
