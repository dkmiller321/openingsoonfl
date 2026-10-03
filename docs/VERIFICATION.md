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

### Stage 1 · 2026-10-03 · Weekly licence import + lead sheet
- `uv run ruff check .` -> All checks passed. `uv run pytest tests -q` -> 31 passed (UT-01..09).
- `uv run pytest e2e -m "stage0 or stage1" -q` -> 7 passed; second run -> 7 passed.
- First run failed E2E-03..06: `dict(session.execute(...))` on a Result raised `TypeError: 'ChunkedIteratorResult' object is not subscriptable`; fixed in `ingest._find_or_create_lead`.
- MCP walkthrough (port 8002, `osfl_walk`), seeded with curl: plan_review_0901 -> 3 leads; weekly_w1 -> rows_fetched 6, rows_new 5, leads_created 4; `/test/leads` read in the browser:
  - E2E-03: pass — SALT & SMOKE BBQ/COASTAL TACOS new, THE ROCKET DINER ownership_change, SPACECOAST WAFFLES mobile, all Licensed, days_ahead 0, phones 321-555-0101..0104; no vending or Orange lead.
  - E2E-04/05/06: covered by pytest only (API/CLI, no UI).
- Real sheet (live DBPR, 3 polite downloads, 7.7 s total): `osfl import-weekly` -> fetched 3157 rows, 82 new Brevard raw records, 77 leads; `osfl import-plan-review` -> fetched 11319 rows, 277 new, 174 leads created, 31 merged into licensed leads. `osfl export-csv --since 2026-09-26` -> 7 leads (3 new + 2 food trucks in plan review, 2 ownership changes), all 7 with a phone or email. Since 2026-07-01: 79 leads. Files in `exports/` (git-ignored).

### Stage 2 · 2026-10-03 · Plan review import + merge
- No new code beyond stage 1: the plan-review source shares the fetch/parse/ingest pipeline.
- `uv run pytest e2e -m stage2 -q` -> 6 passed (E2E-07, -08, -09, -09b, -10, -11); with stages 0-1: 13 passed, twice.
- MCP walkthrough, after weekly_w2 at 2026-10-05T10:00Z:
  - E2E-07: pass — BANANA RIVER BAGELS Applied, 321-555-0302, bagels@example.com; VIERA NOODLE BAR email empty.
  - E2E-08: pass — 8 leads; INDIAN RIVER PHO Licensed, first 2026-09-01, licensed 2026-09-29, 28 days ahead, phone 321-555-0201, email owner@indianriverpho.example, events Applied@2026-09-01, Licensed@2026-09-29.
  - E2E-09/09b/10/11: pytest only (no UI).
