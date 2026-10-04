---
name: "career-data-toolkit"
displayName: "Career Data Toolkit"
description: "Engineering knowledge for InternPilot AI career data: skill and job normalization, the deterministic match score and its explanation, and resume-to-job analysis."
keywords: ["skill normalization", "job normalization", "match score", "match explanation", "resume analysis", "internship", "career data"]
author: "InternPilot AI maintainers"
---

# Career Data Toolkit

Knowledge Power for the InternPilot AI codebase. It explains how career data is normalized, scored and explained so agents change the project code correctly. It contains no runnable app logic and no MCP server.

`plugin.json` is the primary manifest (Agent Plugins 1.0.0). This file is the legacy-format overview, kept so Kiro builds that only read `POWER.md` still load the Power.

## When to load which skill

| Task | Skill |
|---|---|
| Ingestion normalizers, seed jobs, skill catalog or aliases, dedupe | `skills/job-normalization/SKILL.md` |
| Resume skill extraction, missing keywords, suggestion rules | `skills/resume-analysis/SKILL.md` |
| Scoring factors, rounding, reasons, `match_explanation`, anything that shows a score | `skills/match-explanation/SKILL.md` |

Exact scoring rules: `references/scoring-rules.md` (copy of `design.md` §5.1–5.6, `algorithm_version` 1.0.0).

## Ground rules

- `.kiro/specs/internship-intelligence/design.md` is the source of truth. If this Power and the spec disagree, the spec wins and this Power must be fixed in the same commit.
- Matching is one engine: `compute_match` in `backend/app/services/matching/engine.py`. Never re-implement scoring elsewhere (services, routes, frontend).
- The engine is pure: no I/O, no clock, no randomness, `fractions.Fraction` arithmetic, frozen dataclasses in and out.
- Any rule change bumps `algorithm_version` and updates `references/scoring-rules.md` and `design.md` together.
