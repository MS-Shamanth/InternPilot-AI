---
name: job-normalization
description: Normalize skills and job postings for InternPilot AI. Use when editing the skill catalog or aliases, profile skill storage, ingestion normalizers (Remotive, Arbeitnow, normalized/seed format), seed jobs, employment type or experience inference, or job dedupe fingerprints.
---

# Job and skill normalization

Every skill string in the system (profile, job, resume, ingestion) goes through one function, `normalize_skill`. Every external job goes through a format normalizer, then Pydantic `JobCreate`, then dedupe. Source of truth: `design.md` §5.1 and §11.

## Implemented in

| Concern | File / function |
|---|---|
| Skill normalization | `backend/app/services/matching/normalization.py`: `normalize_skill`, `normalize_skills`, `display_skill` |
| Catalog and aliases | `backend/app/services/matching/skill_catalog.py`: `CATALOG`, `ALIASES`, `AMBIGUOUS_RESUME_TERMS` |
| Job sources | `backend/app/services/ingestion/sources.py`: `HttpFetcher`, `RemotiveSource`, `ArbeitnowSource`, `PayloadSource`, `FixtureSource` |
| Format normalizers | `backend/app/services/ingestion/normalizers.py` |
| Dedupe and persistence | `backend/app/services/ingestion/service.py`: `IngestionService.ingest` |
| Skill rows | `backend/app/repositories/skill_repository.py`: `get_or_create_many` (by normalized name) |

## Skill normalization steps (`normalize_skill`)

1. `unicodedata.normalize("NFKC", raw).casefold()`.
2. Collapse every whitespace run to one space.
3. Repeat until stable: strip whitespace; strip edge characters in `EDGE_PUNCTUATION` (`` ,;:|/\()[]{}"'` ``, including the backtick); strip one trailing `.`.
4. Replace with `ALIASES[value]` if present.
5. Return `None` if empty or longer than 50 characters.

The whole sequence repeats until the value no longer changes, so the function is idempotent.

Examples:

| Input | Output |
|---|---|
| `" React ,"`, `"( React )"`, `"React."`, `"ReactJS"`, `"react.js"` | `react` |
| `"Node"`, `"NodeJS"` | `node.js` |
| `"C++"`, `"C#"`, `".NET"` | `c++`, `c#`, `.net` (internal/leading symbols kept) |
| `"Ｐｙｔｈｏｎ３"` (full-width) | `python` (NFKC → `python3` → alias) |
| `"(,)"`, `""`, 51+ characters | `None` |

Display: `display_skill("postgresql") == "PostgreSQL"` from `CATALOG`; unknown names title-case each word's first character (`"apache kafka"` → `"Apache Kafka"`).

## Rules

- Never compare raw skill strings. Normalize both sides, then compare sets.
- Profile input rejects skills that normalize to `None` (422 with `loc` at the index); the engine and ingestion silently drop them.
- `S`, `R`, `P` are frozensets; `P = preferred − R` (a skill in both lists counts only as required).
- Adding an alias: the value must already be a `CATALOG` key, must be a fixed point of steps 1–3, and must not itself be an alias key. `test_skill_catalog.py` asserts this.
- Adding a catalog skill: add `canonical → Display` to `CATALOG`; canonical names are lowercase and already normalized.

## Job normalizers

| Format | Mapping |
|---|---|
| Remotive | `external_id=str(id)`, `company=company_name`, `location=candidate_required_location or "Remote"`, `work_mode=remote`, `job_type` → `full_time/part_time/contract/internship` (`freelance → contract`, other → `full_time`), `application_url=url`, required = normalized `tags` (max 15), preferred = catalog skills found in the description not already required (max 10) |
| Arbeitnow | `external_id=slug`, `work_mode = remote if remote else onsite`, `job_types` containing `intern`/`praktikum` → internship, `part` → part_time, `contract`/`freelance` → contract, else full_time; tags → required, description skills → preferred |
| Normalized (seed) | Fields as in the jobs table; `deadline` (date) or `deadline_in_days` resolved against `clock.today()` |

All formats:

- Strip HTML with an `html.parser`-based extractor, unescape entities, collapse whitespace, truncate descriptions to 20,000 characters.
- Title containing `intern`/`internship`/`trainee` forces `employment_type=internship`.
- Missing `experience_level` is inferred from title tokens: `intern|internship|trainee → internship`, `graduate|entry|new grad → entry`, `junior|jr → junior`, `mid|intermediate → mid`, `senior|sr|lead|principal|staff → senior`, else `null`.
- Validate with `JobCreate`: title/company/location 1–200, `application_url` http(s) ≤ 500, ≤ 30 required and ≤ 30 preferred skills, salaries ≥ 0 with min ≤ max, currency `^[A-Z]{3}$`. Invalid items become `Rejection(index, reason)`; they never abort the batch.

## Dedupe

`fingerprint = sha256(f"{n(title)}|{n(company)}|{n(location)}")`, `n` = casefold, non-alphanumerics → space, collapse, strip. Per item, in input order, one transaction:

1. Same `(source, external_id)` exists → update (unless the new fingerprint belongs to a different job → `duplicates`).
2. Else same fingerprint exists (any source) → `duplicates`.
3. Else insert → `created`. Fingerprints of earlier inserts in the batch are tracked.

Fetch and validate everything before the first write; a source failure never causes a partial write.

## Pitfalls

- Treating `"Node"` and `"Node.js"` as different skills, or `"Java"` and `"JavaScript"` as the same.
- Using `str.lower()` instead of `casefold()` + NFKC; full-width and German `ß` inputs break.
- Stripping internal punctuation (`node.js` → `nodejs`, `c++` → `c`).
- Accepting caller-supplied URLs or file paths in ingestion. Sources are fixed; hosts are allow-listed (`remotive.com`, `www.arbeitnow.com`), HTTPS only, no redirects, size-capped.
- Rendering fetched HTML. Store text only.
- Reading the clock inside a normalizer other than through the injected `Clock` (`deadline_in_days`).

## Tests

- Existing: `backend/tests/unit/test_normalization.py`, `backend/tests/unit/test_skill_catalog.py`, `backend/tests/property/test_normalization_properties.py` (idempotence over arbitrary text and punctuation-wrapped catalog names).
- Planned with ingestion (tasks 2.14, 2.18): normalizer, fingerprint and `HttpFetcher` guard unit tests (`httpx.MockTransport`); integration tests for update-by-external-id, fingerprint skip and `test_ingest_same_source_new_external_id_same_fingerprint_counts_duplicate`.
- Run: `pytest backend/tests/unit/test_normalization.py backend/tests/unit/test_skill_catalog.py backend/tests/property -v`.
