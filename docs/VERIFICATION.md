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

### Stage 3 · 2026-10-03 · Admin console
- `uv run ruff check .` -> All checks passed. `uv run pytest tests -q` -> 31 passed.
- `uv run pytest e2e -m stage3 -q` -> 7 passed on the first run.
- `uv run pytest e2e -m "not smoke and (stage0 or ... or stage3)" -q` -> 20 passed, then **1 failed** (E2E-16, "Active" after unticking): flaky 2 of 4 runs. Cause: FastAPI 0.142 runs `yield` dependency teardown (our commit) *after* the response is sent by default, so the redirect's GET could read the old row. Fix: `DbSession = Annotated[Session, Depends(get_session, scope="function")]`. After: E2E-16 8/8; stages 0-3 -> 20 passed, twice.
- MCP walkthrough (port 8002, standard dataset, then weekly_w2):
  - E2E-12: pass — /leads redirected to /login; "wrong" -> "Wrong password" (401); correct password -> dashboard.
  - E2E-13: pass — stats 4 / 3 / 0; dbpr_weekly green, dbpr_plan_review amber.
  - E2E-14: pass — filter Applied -> 3 rows (Banana River Bagels, Indian River Pho LLC, Viera Noodle Bar), lead time "—"; URL keeps `stage=Applied`. Screenshot `logs/walk-stage3-leads-applied.png`.
  - E2E-15: pass — INDIAN RIVER PHO: Licensed, "28 days ahead", timeline Sep 1 (plan review) / Sep 29 (licensed), two raw records, contact 321-555-0201 / owner@indianriverpho.example / INDIAN RIVER PHO LLC. Screenshot `logs/walk-stage3-lead-detail.png`. Polish found here: raw records now list columns in DBPR's header order (JSONB had reordered them).
  - E2E-16: pass — "not-an-email" -> "Enter valid email addresses" (422); Space Coast POS created, Active, POS, Brevard, Weekly.
  - E2E-17: pass — `/leads.csv?stage=Applied` -> `leads-2026-10-05.csv` (clock date), §1.5 header, Applied rows only with empty days_ahead.
  - E2E-18: first attempt hit a 500 because the walk server was still running pre-change Python with the updated template (my change mid-walk, not an app bug). After restart: pass — display name "Viera Noodle Bar & Grill", note saved, Hide -> Unhide button, list shows "6 leads".

### Stage 4 · 2026-10-03 · Digests
- `uv run ruff check .` -> All checks passed. `uv run pytest e2e -m stage4 -q` -> 6 passed on the first run.
- `uv run pytest e2e -m "not smoke and not stage5" -q` -> 26 passed; second run -> 26 passed.
- MCP walkthrough (port 8002), E2E-19 chained as the operator would:
  - E2E-19: pass. Plan reviews (2026-09-01) -> Space Coast POS created in the UI -> preview showed "3 new restaurants in Brevard - week of Aug 31, 2026" (screenshot `logs/walk-stage4-digest-preview.png`). Clock 2026-09-07T11:00Z, `send-digests-weekly` -> 1 email to pos@example.com, "3 new restaurants in Brevard - week of Sep 7, 2026", `leads-2026-09-07.csv` (header + 3 rows), "application in progress" x3. Imported weekly_w1 + weekly_w2, clock 2026-10-05T11:00Z -> "5 new restaurants in Brevard - week of Oct 5, 2026", contains "Food truck" and "Ownership change", no Indian River Pho. Deliveries: INDIAN RIVER PHO -> Space Coast POS on 2026-09-07; lead licensed 2026-09-29, 28 days ahead.
  - E2E-20: pass — re-running `send-digests-weekly` in the same week -> `{"emails_sent":0}`.
  - E2E-22: pass — "Send test to me" -> "Test sent to operator@example.com"; outbox "[TEST] 0 new restaurants in Brevard - week of Oct 5, 2026" (all leads already delivered, so 0 is right).
  - E2E-23: pass — unsubscribe link from the digest -> "You're unsubscribed from OpeningSoon FL digests."; vendor shows Inactive.
  - E2E-21, E2E-24: pytest only.

### Stage 5 · 2026-10-03 · Source health, schedule
- First run of `uv run pytest e2e -m stage5 -q` -> 5 passed, 1 failed: E2E-30 expected check-health at 09:45Z, but §1.5 says ":15". Asked the user, who approved fixing the assertion to 10:15Z (DECISIONS D7). After: 6 passed.
- `uv run ruff check .` -> All checks passed; `uv run pytest tests -q` -> 31 passed.
- `uv run pytest e2e -m "not smoke" -q` -> 32 passed; second run -> 32 passed.
- MCP walkthrough (port 8002, restarted on current code):
  - E2E-26: pass — weekly_w1 then weekly_empty -> alert "[OpeningSoon FL] Source problem: dbpr_weekly - zero rows"; /sources shows dbpr_weekly red with the "zero rows" run. Screenshot `logs/walk-stage5-sources-red.png`.
  - E2E-29: pass — uploaded weekly_w2/newfood.csv through the file chooser -> "3 rows, 1 new leads" (Indian River Pho merged, the caterer ignored); dbpr_weekly back to green after the good run.
  - E2E-28: pass — `check-health` at 2026-10-07T03:00Z -> plan review amber, 1 alert; at 2026-10-14 -> weekly amber too, 1 alert; repeat -> 0 alerts.
  - E2E-30: pass — `/test/schedule` at 2026-10-14T12:00Z -> check-health 12:15Z, weekly digest Monday 2026-10-19T11:00Z.
  - E2E-19 (re-walked): pass — vendor created in the UI; "3 new restaurants in Brevard - week of Sep 7, 2026" includes Indian River Pho; "5 new restaurants in Brevard - week of Oct 5, 2026" doesn't; delivered 2026-09-07.
  - E2E-25, E2E-27: pytest only.
