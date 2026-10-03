# KIT_FEEDBACK.md — self-improvement log

A running log of problems hit while building from this kit (`CLAUDE.md`, `KICKOFF.md`, `docs/PRD.md`, `docs/E2E_TESTS.md`, `.env.example`). Each entry records what happened, what it cost, and a concrete change for the next kit. Add entries as they happen, under a dated heading per stage. Also record what worked well and should be kept.

Kit: `idea-to-build-kit` v1.1.0 · Project: OpeningSoon FL

Tags: **[env]** machine/setup · **[contract]** E2E_TESTS.md · **[prd]** PRD gaps · **[process]** CLAUDE.md/KICKOFF workflow · **[stack]** library/version surprises · **[source]** DBPR site/format surprises · **[agent]** your own mistakes

Entry format:

```
N. **[tag] One-line summary.** What happened.
   - *Cost:* time, failed runs, questions to the user.
   - *Kit change:* the specific edit that would have prevented it.
```

## Log

### 2026-10-03 · Kickoff and stage 0

1. **[source] The kit planned a licence-search scrape, but DBPR publishes the early signal as a free CSV.** `HR_plan_review.csv` lists plan reviews with owner phone/email a median 78 days before the licence (36/39 Brevard licences matched); `newfood.csv`/`chgownr_food.csv` cover licences. The spike found it in minutes.
   - *Cost:* one stop-and-ask, then rewriting the PRD, fixtures, ~15 scenarios, CLAUDE.md, KICKOFF.md and .env.example before any spec existed.
   - *Kit change:* in Phase 1/2, before writing the PRD, look at the agency's public-records download page for the data in question; prefer bulk files over scraping and name the exact files in the PRD.

2. **[env] Ports 8000 and 55432 were already taken by another project's containers (LaunchLedger).** Kit hard-coded both.
   - *Cost:* small; moved Compose to 8010/55433 (DECISIONS D5).
   - *Kit change:* make host ports `.env` variables in the kit (`APP_HOST_PORT`, `POSTGRES_HOST_PORT`) and have preflight suggest free ones instead of just failing.

3. **[contract] E2E-12 says login "lands on the dashboard" even when the user was redirected from `/leads`.** A `next=` redirect (the usual pattern) would land on `/leads` and fail the spec.
   - *Cost:* small; login always goes to `/`.
   - *Kit change:* say explicitly "login always redirects to /" or drop "lands on the dashboard" from E2E-12.

4. **[agent] A conftest helper named `tests_db_url` was collected as a test** (pytest's `test*` prefix matches `tests_`).
   - *Cost:* one confusing collect run.
   - *Kit change:* tell builders to keep helper names in conftest off the `test` prefix.

5. **[env] The app reads `.env` by default, so the "missing ADMIN_PASSWORD" spec (E2E-01) can't fail startup while `.env` sets it.** Added `OSFL_ENV_FILE` (empty = environment only) and the test env sets it.
   - *Cost:* small, caught in design.
   - *Kit change:* specify a way to disable the dotenv file for tests in the settings section of CLAUDE.md.

## Sending this log to KitForge (final acceptance step 8)

Send exactly one report. Each log entry becomes one `corrections` item (`text` = the entry with its tag, cost and kit change; `quote` = the user's own words if the user corrected you, else omit it). Use the final test totals.

Write the JSON to `logs/kitforge-report.json`, then post the file. (Piping a heredoc into `curl -d @-` returned `invalid_json` from Git Bash on Windows.)

```json
{
  "kit": "idea-to-build-kit",
  "version": "1.1.0",
  "project_path": "<absolute path of this repo, forward slashes>",
  "outcome": "<success | partial | failed>",
  "corrections": [
    { "text": "<[tag] entry text, cost and kit change>" }
  ],
  "tests": { "passed": 0, "failed": 0 }
}
```

```bash
curl -s -X POST http://127.0.0.1:4317/api/runs/report -H "content-type: application/json" --data-binary @logs/kitforge-report.json
```

- `outcome`: `success` if every P0 scenario passes and final acceptance completed; `partial` if done with spec changes, skips or known issues; `failed` if abandoned.
- If the command fails (KitForge is not running), say so in one line and stop. Do not retry.
