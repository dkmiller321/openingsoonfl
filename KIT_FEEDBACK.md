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

(no entries yet)

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
