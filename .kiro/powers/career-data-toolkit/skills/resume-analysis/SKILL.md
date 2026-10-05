---
name: resume-analysis
description: Compare a resume against a specific InternPilot AI job. Use when editing resume skill extraction, ambiguous short terms (Go, R, REST), matching/missing skills, relevant projects, missing keywords, suggestion rules or the compatibility score of POST /api/resume/analyze.
---

# Resume-to-job analysis

`ResumeService.analyze(user, job_id, resume_text | None)` extracts skills from resume text, compares them with the job's required and preferred skills, and returns measurable gaps plus rule-based suggestions. It never rewrites or stores a modified resume. Source of truth: `design.md` §9, R8.

## Implemented in

| Concern | File / function |
|---|---|
| Service and extraction | `backend/app/services/resume_service.py`: `ResumeService.analyze` |
| Catalog, aliases, ambiguous terms | `backend/app/services/matching/skill_catalog.py`: `CATALOG`, `ALIASES`, `AMBIGUOUS_RESUME_TERMS` |
| Score | `backend/app/services/matching/engine.py`: `compute_match` (same engine as job lists) |
| Schemas | `backend/app/schemas/resume.py`: `ResumeAnalyzeRequest`, `ResumeAnalysis` |
| Route | `backend/app/api/routes/resume.py`: `POST /api/resume/analyze` |

## Steps

1. Pick the text: request `resume_text` if it is non-blank, else the profile's `resume_text`. `None`, `""` and whitespace-only are all "blank". Both blank → `ResumeEmptyError` (422 `RESUME_EMPTY`). Record `resume_source` = `request` | `profile`.
2. Build two views: `nfkc` (NFKC + whitespace collapse, case kept) and `folded` (`nfkc.casefold()`).
3. Terms = `CATALOG` keys ∪ all `ALIASES` keys ∪ `skills.normalized_name` from the DB ∪ the job's skills. For each term, search with `(?<![A-Za-z0-9+#.])` + `re.escape(term)` + `(?![A-Za-z0-9+#])`.
   - Terms in `AMBIGUOUS_RESUME_TERMS` (`go, golang, rest, node, js, ts, py, ml, dl, r, c`) are searched case-sensitively in `nfkc`, once per accepted casing (`go → {Go, Golang}`, `rest → {REST}`, `r → {R}`, …).
   - Every other term, including multi-word terms that contain an ambiguous word (`rest apis`, `node.js`), is searched in `folded`.
   - Map matches to canonical names → `resume_skills`.
4. Compare with `R` (required) and `P` (preferred − required), both normalized:
   - `matching_skills` = `(R ∪ P) ∩ resume_skills` → `{skill, is_required}`.
   - `missing_skills` = `(R ∪ P) − resume_skills` → `{skill, is_required, in_profile}`.
   - `relevant_projects` = profile projects whose technologies ∩ `R ∪ P` ≠ ∅ → `{name, matched_skills[], mentioned_in_resume}` (case-insensitive name search).
5. `missing_keywords`: description tokens matching `[a-z][a-z0-9+#.]{2,}` (casefolded), trailing `.` stripped, length ≥ 3, not stop words, not in the resume; keep frequency ≥ 2 or catalog skills; sort by frequency desc then alphabetically; max 15.
6. `compatibility_score` and `match_explanation` = `compute_match(profile with technical_skills = resume_skills, job)`. Same engine, so the number is comparable with the job's match score.
7. Suggestions, in this rule order, then evidence alphabetically:

| Rule | Trigger | Message |
|---|---|---|
| `ADD_PROFILE_SKILL` | missing skill with `in_profile=true` | `Your profile lists {Skill}, which this role requires/prefers, but your resume does not mention it.` |
| `GAP_REQUIRED_SKILL` | missing required skill, `in_profile=false` | `{Skill} is required and not evidenced; consider a project or course that demonstrates it.` |
| `MENTION_PROJECT` | relevant project not mentioned | `Mention your project "{name}"; it uses {skills}.` |
| `ADD_KEYWORDS` | ≥ 3 missing keywords | `Consider reflecting these job terms where truthful: {top 5}.` |
| `QUANTIFY` | < 3 numeric tokens (digits or `%`) | `Add measurable outcomes (numbers, percentages); found {n}.` |
| `LENGTH_SHORT` / `LENGTH_LONG` | < 150 / > 1,200 words | `Resume has {n} words; aim for 300–900 for early-career roles.` |
| `ADD_LINKS` | GitHub/portfolio URL in profile but not in resume | `Add your {GitHub/portfolio} link.` |

## Examples

| Resume text | Extracted |
|---|---|
| `"Built services in Go"` | `go` |
| `"go to market strategy"` | nothing (lowercase `go` is English) |
| `"built REST APIs"` | `rest apis` |
| `"the rest of the team"` | nothing |
| `"R and Python"` | `r`, `python` |
| `"JavaScript and TypeScript"` | `javascript`, `typescript` (never `java`) |
| `"C++ and C#"` | `c++`, `c#` |

## Rules

- Recommendations come only from measurable differences (skills, projects, keywords, counts, links). No subjective advice, no generated resume text.
- `compatibility_score` must come from `compute_match`; never compute a separate resume score.
- Skill lists are display names (`display_skill`) sorted by normalized name.
- Never log resume text.

## Pitfalls

- Substring matching (`java` inside `javascript`, `c` inside every word). Always use the boundary regex.
- Matching ambiguous terms casefolded: "go", "rest", "r" appear in normal English.
- Treating whitespace-only request text as present and skipping the profile fallback.
- Mutating or saving the resume during analysis.
- Ordering suggestions by dict/set iteration order instead of rule order then evidence.

## Tests

- Existing: `backend/tests/unit/test_skill_catalog.py` covers `AMBIGUOUS_RESUME_TERMS` and catalog invariants.
- Planned with task 4.7/4.11: unit tests for each extraction example above, each suggestion rule and its ordering, keyword rules (`"python."` → `python`), whitespace-only fallback and `RESUME_EMPTY`; API tests for 200/404/422 in `backend/tests/api/`.
- Run: `pytest backend/tests/unit -k resume -v` once those exist; the Postman "Resume" folder checks the live endpoint.
