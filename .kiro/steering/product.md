---
inclusion: always
---

# Product: InternPilot AI

## Purpose

InternPilot AI is an AI-powered internship and career command center. It helps students and fresh graduates discover opportunities, see a transparent 0–100 match score with the exact reasons behind it, track applications, prepare for interviews and compare their resume against a specific role. The product earns trust through explainability: every number on screen can be traced to a rule.

Specs live in `.kiro/specs/internship-intelligence/`. When behavior is unclear, `requirements.md` wins over this file.

## Target users

- **Students** looking for internships (primary).
- **Fresh graduates** applying to entry-level and junior roles.
- **Career switchers** with project experience but little industry history (secondary).

They apply to many roles at once, lack recruiter feedback, and need to know what to improve next.

## UX principles

1. **Explain, don't just score.** A score is always shown with its reasons (`+`/`-`) and factor breakdown. Never display a score without a way to see why.
2. **Actionable over decorative.** Every screen answers "what should I do next?" (missing skills, upcoming deadlines, next status).
3. **Calm, professional SaaS look.** Teal "pilot" primary, amber accent, slate neutrals; generous whitespace; no neon gradients or generic "AI" glow.
4. **Fast and forgiving.** Loading skeletons, clear empty states with a next action, error states with retry, toasts for every mutation.
5. **Accessible by default.** Labelled controls, visible focus, keyboard-operable everything (including Kanban moves), color never the only signal.
6. **Honest.** No placeholder features presented as complete; the app works offline on seeded data and says when external sources fall back.

## Core terminology

Use these terms consistently in UI copy, code and docs.

| Term | Meaning |
|---|---|
| Profile | The user's career data: skills, roles, locations, education, projects, resume. |
| Job / Opportunity | A discovered role. UI says "Opportunity" in marketing copy, "Job" elsewhere. |
| Match score | Integer 0–100 from the deterministic engine. Displayed as `MATCH SCORE: 87/100`. |
| Match explanation | `match_explanation` object: factors, matched/missing skills, positive/negative reasons. |
| Factor | One weighted component of the score (required skills 35, preferred 10, role 15, experience 15, location 10, work mode 5, education 5, projects 5). |
| Matching job | A non-hidden job with score ≥ 60. |
| Application | Tracker record for one job with exactly one status. |
| Status | `Saved`, `Interested`, `Applied`, `Assessment`, `Interview`, `Rejected`, `Offer`, `Withdrawn` (exact casing). |
| Bookmark | Per-user flag on a job; does not create an application. |
| Hide | Per-user flag that removes a job from lists and recommendations. |
| Ingestion | Importing jobs from a public API, a captured MCP payload or fixtures. |
| Demo user | The single seeded identity; not real authentication. |

## Product constraints

- Core features (matching, resume analysis, interview prep, dashboard) are deterministic and must work with no network and no LLM.
- An optional LLM may only enrich interview questions; it never affects scores or metrics.
- Never scrape LinkedIn or sites that prohibit automated access. Sources: public no-auth APIs (Remotive, Arbeitnow), local fixtures, user/MCP-supplied payloads.
- Never rewrite the user's resume; give recommendations tied to measurable differences.
- The app must be fully demoable from `docker compose up` with seeded data.
- Single demo user; production auth is out of scope and must be labelled as such.
