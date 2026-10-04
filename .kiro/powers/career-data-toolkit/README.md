# career-data-toolkit

Custom Kiro Power for InternPilot AI. It packages engineering knowledge about career data (skill normalization, job normalization, match scoring and explanations, resume analysis) as three Agent Skills plus an exact copy of the scoring rules.

```
career-data-toolkit/
  plugin.json                         Agent Plugins 1.0.0 manifest (Kiro fields under extensions["dev.kiro"])
  POWER.md                            legacy-format overview and front matter
  skills/job-normalization/SKILL.md
  skills/resume-analysis/SKILL.md
  skills/match-explanation/SKILL.md
  references/scoring-rules.md         design.md §5.1-5.6, algorithm_version 1.0.0
```

- Activation keywords: skill normalization, job normalization, match score, match explanation, resume analysis, internship, career data.
- Used by `backend-agent` (`.kiro/agents/backend-agent.json` lists the skills as resources) and by any Kiro chat that mentions the keywords.
- Knowledge only: the implementation lives in `backend/app/services/matching/`, `backend/app/services/ingestion/` and `backend/app/services/resume_service.py`.
- Why `displayName` and `skills` sit under `extensions`: the Agent Plugins 1.0.0 manifest schema is closed (only `$schema`, `name`, `version`, `description`, `author`, `homepage`, `repository`, `license`, `keywords`, `extensions` are allowed at the top level) and skills are discovered from the fixed `skills/` folder. Client-specific data belongs under a reverse-domain namespace.

Full documentation: `docs/kiro-powers.md`.
