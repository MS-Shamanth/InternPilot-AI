---
name: match-explanation
description: Compute and explain the InternPilot AI match score (0-100). Use when editing compute_match, factor weights or ratio rules, Fraction rounding, positive/negative reason templates, the match_explanation response, MatchScoreRing or MatchExplanationPanel, or the P1-P5 matching property tests.
---

# Match score and explanation

One pure engine, `compute_match(profile: MatchProfile, job: MatchJob) -> MatchResult`, produces the integer score and the `match_explanation`. Job lists, job detail, `POST /api/jobs/{id}/match`, recommendations, dashboard and resume analysis all call it. Exact rules: `../../references/scoring-rules.md` (copy of `design.md` §5).

## Implemented in

| Concern | File / function |
|---|---|
| Inputs/outputs | `backend/app/services/matching/types.py`: `MatchProfile`, `MatchJob`, `ProjectInput`, `MatchResult` (frozen dataclasses) |
| Engine | `backend/app/services/matching/engine.py`: `compute_match` |
| Skill sets | `backend/app/services/matching/normalization.py`: `normalize_skills`, `display_skill` |
| API schema | `backend/app/schemas/match.py`: `MatchExplanation` (1:1 mirror of `MatchResult`) |
| Callers | `job_service.py`, `recommendation_service.py`, `dashboard_service.py`, `resume_service.py` |
| UI | `frontend/src/components/match/{MatchScoreRing,MatchExplanationPanel,FactorBreakdown}.tsx` (display only) |

## Steps

1. Build sets: `S = normalize_skills(profile.technical_skills)`, `R = normalize_skills(job.required_skills)`, `P = normalize_skills(job.preferred_skills) − R`.
2. Compute each factor's `ratio` as a `Fraction` in [0, 1], in this fixed order:

| # | key | weight | ratio (short form; full rules in scoring-rules.md) |
|---|---|---|---|
| 1 | `required_skills` | 35 | `R = ∅` → 1, else `|R ∩ S| / |R|` |
| 2 | `preferred_skills` | 10 | `P = ∅` → 1, else `|P ∩ S| / |P|` |
| 3 | `role_similarity` | 15 | no usable roles or no title tokens → 1/2; else best `|tok(role) ∩ tok(title)| / |tok(role)|` |
| 4 | `experience` | 15 | unknown → 1/2; `gap = job − user`: ≤ 0 → 1, 1 → 3/5, 2 → 1/5, ≥ 3 → 0 |
| 5 | `location` | 10 | remote → 1; no candidates → 1/2; first segment match → 1; last segment (country) → 1/2; else 0 |
| 6 | `work_mode` | 5 | no preference → 1/2; preferred → 1; hybrid not preferred → 1/2; else 0 |
| 7 | `education` | 5 | no job minimum → 1; user unknown → 1/2; `user ≥ job` → 1; one below → 1/2; else 0 |
| 8 | `projects` | 5 | `J = R ∪ P = ∅` → 1/2; relevant project groups `k`: 0 → 0, 1 → 3/5, ≥ 2 → 1 |

3. `points = weight × ratio` (exact). `total = Σ points`. `score = clamp(floor(total + 1/2), 0, 100)` (half-up on exact values; no floats).
4. Emit reasons per factor using the exact templates in scoring-rules.md §5.4, ordered by factor order, then alphabetically by normalized skill inside factors 1–2.
5. Fill skill lists (display names sorted by normalized name) and `detail` strings; always return all 8 factors.
6. Serialize: `points` rounded to 2 decimals, `ratio` to 4, `algorithm_version: "1.0.0"`.

## Worked example

Profile: skills `React, TypeScript, Python`; target role `Frontend Engineer`; location `Bengaluru, India`; preferred modes `remote`; level `internship`; education `bachelor`; one project "Campus Event Hub" using `React`.
Job: `Frontend Engineering Intern`, `Bengaluru, India`, `hybrid`, level `internship`, min education `bachelor`; required `React, TypeScript, CSS`; preferred `Jest`.

| Factor | Ratio | Points |
|---|---|---|
| required_skills | 2/3 | 70/3 ≈ 23.33 |
| preferred_skills | 0 | 0 |
| role_similarity | `tok("Frontend Engineer") = {frontend, engineer}`, `tok(title) = {frontend, engineering}` → 1/2 | 15/2 = 7.5 |
| experience | gap 0 → 1 | 15 |
| location | first segment `bengaluru` matches → 1 | 10 |
| work_mode | hybrid, not preferred → 1/2 | 5/2 = 2.5 |
| education | user = job → 1 | 5 |
| projects | 1 relevant group → 3/5 | 3 |

`total = 70/3 + 0 + 15/2 + 15 + 10 + 5/2 + 5 + 3 = 70/3 + 43 = 199/3 ≈ 66.33`, so `score = floor(199/3 + 1/2) = floor(66.83…) = 66`. (Hand-computed from §5.3; the engine's example-based unit tests are authoritative.)

Reasons (positive, factor order): `React matches required skill`, `TypeScript matches required skill`, `Job title partially matches your target role "Frontend Engineer"`, `Your internship experience meets the internship level`, `Bengaluru, India matches your location or preferred locations`, `Hybrid work partially matches your preference`, `Your education meets the bachelor's requirement`, `Project "Campus Event Hub" uses React`.
Reasons (negative): `CSS experience is missing (required)`, `Jest is a preferred skill not in your profile`.

UI shows `MATCH SCORE: 66/100` with `+`/`−` prefixes added by the frontend.

## Rules

- Only factors 1–2 read `S`; adding a skill outside `R ∪ P` changes nothing (P2). Projects use project technologies, never `S`.
- No I/O, clock, randomness, models or repositories in the engine. Inputs are raw strings; normalization is part of the unit.
- Deterministic and order-independent: sets, sorted outputs, total-order tie-breaks for best role and project display name (P5).
- Never compute a score outside the engine (frontend, SQL, services) and never cache it without the profile's `updated_at` in the key.
- The optional LLM never touches scores.
- Rule change → bump `algorithm_version`, update `design.md` §5 and `references/scoring-rules.md` in the same commit.

## Pitfalls

- Float arithmetic (`0.1 + 0.2`) or Python `round()` (banker's rounding). Use `Fraction` and `floor(total + 1/2)`.
- Counting a skill listed as both required and preferred twice.
- Division by zero when every target role is stop tokens (`"Intern"`) or `R`/`P` is empty; those are the neutral/full-credit cases.
- `"Engineering"` does not equal `"engineer"` after tokenization (only `developer/dev/programmer → engineer` are mapped); do not add stemming without a spec change.
- Showing a score without its reasons in the UI (product rule: explain, don't just score).
- Asserting on reason order that depends on dict/set iteration.

## Tests

- Existing: normalization unit tests (`backend/tests/unit/test_normalization.py`) and `backend/tests/property/test_normalization_properties.py`.
- Planned with tasks 4.11 and 5.1–5.6: example-based unit tests for every factor case and reason template in `backend/tests/unit/`; properties in `backend/tests/property/test_matching_properties.py`: `test_p1_score_is_bounded`, `test_p2_adding_matching_skill_never_lowers_score`, `test_p2_adding_unrelated_skill_changes_nothing`, `test_p3_duplicate_skills_have_no_impact`, `test_p4_missing_required_skills_get_no_credit`, `test_p5_match_is_deterministic_and_order_independent`; frontend `MatchScoreRing` and `MatchExplanationPanel` tests in `frontend/tests/`.
- Coverage gate: `app/services/matching/` ≥ 95% (`pytest --cov=app --cov-report=term-missing`).
- Run: `pytest backend/tests/property -v`.
