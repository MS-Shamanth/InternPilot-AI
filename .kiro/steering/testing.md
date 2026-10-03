---
inclusion: always
---

# Testing

Every feature ships with tests at the right level. A change is not done until `pytest` and `npm test` pass and lint is clean.

## Layout

| Kind | Location | Runs with |
|---|---|---|
| Backend unit | `backend/tests/unit/` | `pytest backend/tests/unit` |
| Backend integration (repositories, services, DB constraints) | `backend/tests/integration/` | `pytest backend/tests/integration` |
| Backend API (FastAPI `TestClient`) | `backend/tests/api/` | `pytest backend/tests/api` |
| Property-based (Hypothesis) | `backend/tests/property/` | `pytest backend/tests/property -v` |
| Frontend component/interaction (Vitest + Testing Library) | `frontend/tests/` | `npm test` in `frontend/` |

## Unit tests

- Cover every pure function: skill normalization, each matching factor case and reason template, rounding, state-machine transitions, dashboard metric definitions, resume extraction and suggestion rules, interview templates, ingestion normalizers, fingerprinting, HTTP fetch guards.
- One behavior per test; arrange-act-assert; no DB, no network.

## Integration and API tests

- Use a real SQLAlchemy session. Default database is in-memory SQLite; set `TEST_DATABASE_URL` to run the same tests on PostgreSQL. Each test runs in an isolated transaction or fresh schema.
- Cover: job creation and dedupe (source/external_id update, fingerprint skip), seed idempotency, application uniqueness, the status check constraint, cascades, every endpoint's success shape, error envelope, 404/409/413/422, `X-Request-ID`.
- Override FastAPI dependencies (`get_session`, `get_clock`, ingestion sources, LLM provider) instead of patching internals.

## Property-based tests

- Hypothesis profile registered in `backend/tests/conftest.py`: `max_examples=200`, `derandomize=True`, `deadline=None`; shared strategies in `backend/tests/property/strategies.py`.
- Required properties (see `design.md` §17): P1 score bounds, P2 matching-skill monotonicity (+ unrelated skill no-op), P3 duplicate no-impact, P4 missing required skills get no credit, P5 determinism/order independence, P6 status validity.
- Name tests `test_p<n>_<property_in_words>` and cite requirement IDs in the docstring, e.g. `"""P2 — R3.5, R3.6: adding a matching skill never lowers the score."""`.
- When Hypothesis finds a counterexample, add it as an `@example(...)` and fix the code, not the property.

## Frontend tests

- Test behavior through the DOM (roles, labels, text), not implementation details.
- Mock at the `src/api/*` module boundary; never hit a real server.
- Required: `MatchScoreRing` (text + aria-label), `MatchExplanationPanel` (`+`/`-` reasons), `KanbanBoard` (only allowed moves, keyboard Move-to), `JobFilters` URL sync, `api/client` error parsing, dashboard empty state.

## Naming

- Python: `test_<unit>_<condition>_<expected>`, e.g. `test_transition_offer_to_applied_raises`.
- TypeScript: `describe('<Component>')` + `it('<does something> when <condition>')`.

## Coverage

- Backend: ≥ 80% line coverage overall, ≥ 95% for `app/services/matching/` (`pytest --cov=app --cov-report=term-missing`).
- Frontend: ≥ 60% lines for `src/components` and `src/lib`.
- Coverage is a floor, not a goal: every requirement criterion should be traceable to at least one test.

## Determinism

- No network in tests; external sources use `httpx.MockTransport` or fake `JobSource`s.
- Time comes from an injected `FixedClock`; never call `date.today()`/`datetime.now()` in code under test.
- No randomness without a fixed seed; no reliance on dict/set iteration order in assertions on ordered output.
- Tests must pass in any order and in isolation.
