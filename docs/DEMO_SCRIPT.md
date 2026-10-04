# Demo script (about 5 minutes)

Start the stack as in [demo.md](demo.md) and open http://localhost:5173. Everything below runs on seeded data with no network or LLM.

1. **Dashboard.** Point out jobs discovered, matching jobs (score ≥ 60), submitted applications, interviews, offers, response rate, the score distribution chart, upcoming deadlines and top recommendations.
2. **Profile.** Show skills, target roles, locations, education and projects. Add a skill and save; the toast confirms it and scores update.
3. **Jobs.** Search, filter by work mode, sort by match score, set a minimum score. The URL keeps the filters. Bookmark one job and hide another.
4. **Job detail.** Open a job: `MATCH SCORE: n/100`, the factor breakdown and every `+`/`-` reason. Explain that the score is deterministic and the same engine feeds every screen.
5. **Mark as applied.** Use "Mark as applied" on the job; it appears in the tracker as `Applied`.
6. **Applications.** Switch to the Kanban board. Drag a card to an allowed column, then use the keyboard "Move to" menu. Only allowed transitions are offered.
7. **Resume analysis.** Pick a job, run the analysis: matching and missing skills, relevant projects, missing keywords and suggestions with evidence. The resume is never rewritten.
8. **Interview prep.** Open the same job: role, technical, skill, project and HR questions plus prep topics from templates.
9. **API.** Open http://localhost:8000/docs, or run the Postman collection in `docs/postman/`.
10. **Kiro.** Show the spec (`.kiro/specs/internship-intelligence/`), steering, hooks, MCP config, the custom Power and agents. See [KIRO_CHALLENGE_EVIDENCE.md](KIRO_CHALLENGE_EVIDENCE.md).
