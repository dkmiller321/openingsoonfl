# VERIFICATION.md — evidence log

Claude Code appends one section per stage: the stage number, every command run with its pass/fail counts, each scenario walked through the `playwright-headless` MCP server as `E2E-xx: pass | fail — note`, screenshots taken, and anything surprising. Final acceptance adds a summary: totals, skipped tests and why, known issues, live smoke results (including the Brevard record count), and the exact commands to run the app and produce the weekly Brevard sheet. Nothing counts as done unless it is recorded here with the command that proved it.

## Log

### Stage 0 · 2026-10-03 · Skeleton, spike, all specs
- Plan (Phase 1): six stages per PRD; each DBPR source is a fetcher (live httpx, or `FixtureFetcher` reading `fixtures/`) plus a pure parser; leads are matched by `LIC:<digits>` then `K:<name|address|zip>` keys (table `lead_keys`); `first_seen` = earliest event date, stage = most advanced; verification = pytest-playwright + `playwright-headless` walkthrough on port 8002 / `osfl_walk`.
- Spike: found DBPR CSV downloads (DECISIONS D1); user approved swapping the licence-search scrape for `HR_plan_review.csv` and including contacts (D2, D3). PRD, E2E_TESTS.md, CLAUDE.md, KICKOFF.md, .env.example and the living PRD doc updated before specs were written.
- `uv run alembic upgrade head` -> initial schema `4aa15356bfeb` applied on 127.0.0.1:55433.
- `uv run python scripts/build_fixtures.py` -> 19 fixture files + `fixtures/errors.json`; real samples: 39+10 newfood, 43+10 chgownr, 277+10 plan-review rows.
- `uv run pytest e2e --collect-only -q` -> 36 collected (32 scenario specs incl. E2E-09b, 4 smoke).
- `uv run pytest e2e -m stage0 -q` -> 3 passed.
- `PW_TIMEOUT_MS=2000 uv run pytest e2e -m "not smoke" -q` -> 3 passed, 13 failed, 16 errors: every failure is an unbuilt feature (`/test/run/*` 404, no dashboard/leads/vendors pages, no `/test/schedule`).
- MCP: `scripts/walk_server.py start` -> walkthrough server on 127.0.0.1:8002; `browser_navigate` /login + `browser_snapshot` showed heading "OpeningSoon FL", the Password textbox and "Log in" button. Console showed a missing favicon 404 -> added `/static/favicon.svg`.
