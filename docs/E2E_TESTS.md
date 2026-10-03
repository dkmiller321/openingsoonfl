# E2E_TESTS.md — Acceptance contract

Every scenario below becomes a pytest-playwright spec in `e2e/` **before** the feature is built (stage 0). A stage is done when its scenarios, and every earlier stage's scenarios, pass. Then you walk them again through the `playwright-headless` MCP server (§5).

**The most important test is E2E-19.** It proves the product's core promise: a restaurant reaches a vendor's inbox while its application is still in progress, and the vendor never gets the same lead twice.

## 1. Test harness

### 1.1 Running

| Command | What it does |
|---|---|
| `uv run pytest tests` | Unit tests (§4). |
| `uv run pytest e2e -m "not smoke"` | All E2E specs. The `live_server` fixture starts the app on `127.0.0.1:8001` with the test env (§1.2) unless `BASE_URL` is set. |
| `uv run pytest e2e -m stage3` | One stage's scenarios (pytest markers `stage0`…`stage5`, registered in `pyproject.toml`). |
| `BASE_URL=http://127.0.0.1:8000 uv run pytest e2e -m "not smoke"` | Runs against an already-running app, such as the Compose stack started with the test override. |
| `RUN_SMOKE=1 uv run pytest e2e -m smoke` | Live-DBPR smoke suite (§3). Never in normal runs. |

Every spec carries its stage marker, and its function name starts with the scenario id, for example `test_e2e_08_plan_review_and_licence_merge`. Chromium only, headless, run serially (the specs share one database). Keep traces on failure under `test-results/`. pytest-playwright wipes `test-results/` at the start of every run, so server logs go to `logs/`, never there.

### 1.2 The test server

The `live_server` fixture (session scope):

- Launches `uvicorn osfl.main:app --host 127.0.0.1 --port 8001` **with the venv's Python executable**, not through `uv run`, so the process it holds is the real server.
- Fails immediately if port 8001 is already in use, because a stale server would silently test old code.
- Kills the whole process tree on teardown.
- Polls `GET /health` until it returns 200, for at most 30 s.

The test env is: `DATABASE_URL` = `TEST_DATABASE_URL` (database `osfl_test`), `TEST_ROUTES=1`, `SOURCE_MODE=fixture`, `EMAIL_MODE=outbox`, `SCHEDULER_ENABLED=0`, `ADMIN_PASSWORD=test-admin-pw`, `OPERATOR_EMAIL=operator@example.com`, `OPERATOR_POSTAL_ADDRESS=OpeningSoon FL, PO Box 1000, Melbourne, FL 32901`, `APP_BASE_URL=http://127.0.0.1:8001` and `MAX_VENDORS_PER_CATEGORY=2`.

Use `127.0.0.1` everywhere, never `localhost`. On Windows, `localhost` tries IPv6 first and costs about 10 s per Postgres connection.

A helper, `start_app(env_overrides, port)`, starts a throwaway server for the scenarios that need a different env (E2E-01, E2E-02).

### 1.3 Test-only routes

These are mounted only when `TEST_ROUTES=1`. Otherwise every `/test/*` path returns **404**.

| Route | Body | Returns / effect |
|---|---|---|
| `POST /test/reset` | none | Truncates every table, re-seeds `categories`, clears the frozen clock. Returns `{"ok": true}`. Every spec calls it in a fixture before it runs. |
| `POST /test/clock` | `{"now": "2026-09-01T12:00:00Z"}` or `{"now": null}` | Sets or clears the frozen clock (`FAKE_NOW`). All "now" reads in the app go through one `clock.now()`. |
| `POST /test/run/{job}` | `{"fixture": "<name>"}` (source jobs only) | Runs the job **through the same function the CLI and scheduler call**. Source jobs get a `FixtureFetcher` instead of the live fetcher. Jobs: `import-weekly`, `import-plan-review`, `send-digests-weekly`, `send-digests-daily`, `check-health`. |
| `GET /test/leads` | none | All leads, sorted by `business_name`: `[{id, business_name, address, county, lead_type, stage, first_seen, licensed_on, days_ahead, hidden, note, events: [{stage, date, source}]}]`. Dates are ISO `YYYY-MM-DD`, and `days_ahead` is `null` until licensed. |
| `GET /test/state` | none | Row counts: `{leads, raw_records, source_runs, outbox, deliveries, digests}`. |
| `GET /test/outbox` | none | Emails, oldest first: `[{id, to: [..], subject, html, text, attachments: [{filename, content_type, content_b64}], created_at}]`. |
| `GET /test/deliveries` | none | `[{vendor_name, business_name, delivered_on}]`. |
| `GET /test/runs` | none | `source_runs`, newest first: `[{id, source, trigger, status, rows_fetched, rows_new, error}]`. |
| `GET /test/schedule` | none | `[{job, next_run}]`, with `next_run` computed from the current (possibly frozen) clock, in UTC ISO format. |

A source job returns `{run_id, status: "ok"|"failed", rows_fetched, rows_new, leads_created, leads_updated, error}`. A digest job returns `{emails_sent}`. `check-health` returns `{statuses: {source: "green"|"amber"|"red"}, alerts_sent}`.

### 1.4 Fixtures (deterministic DBPR data)

Each source is split into a **fetcher**, which does network I/O and returns raw bytes per file, and a **parser**, a pure function from those bytes to records. In fixture mode only the fetcher is replaced: `FixtureFetcher` reads files from `fixtures/`. The real parser, classifier, matcher, transaction handling and `source_runs` bookkeeping all run.

**Sources** (all plain CSV downloads; URLs and real headers are in `docs/DECISIONS.md` D1):

| Source | Files fetched per run | Stage it produces | Event date column |
|---|---|---|---|
| `dbpr_weekly` | `newfood.csv` (new licences) **and** `chgownr_food.csv` (owner changes), 2 s apart | Licensed | `Application Approval Date ` (note the trailing space in the real header) |
| `dbpr_plan_review` | `HR_plan_review.csv` | Applied | `Review Application Date` |

The two licence files share one 38-column header. A fixture for `dbpr_weekly` is a **directory** holding both files. A fixture for `dbpr_plan_review` is a single CSV. Every canonical fixture uses the **real captured headers and column order** (`fixtures/headers/`), with the rows below filled into the real columns. Columns not listed are left empty, except `Location County` / `County` and `Location State Code` = `FL`.

**Classification:**

| File | Rule | lead_type |
|---|---|---|
| licence files | `Rank Code` SEAT or NOST | new |
| licence files | `Rank Code` MFDV or HTDG | mobile |
| licence files | `Rank Code` CATR or VEND | ignored |
| `chgownr_food.csv` | any non-ignored rank | ownership_change (wins over mobile) |
| plan review | `Transaction` contains `Change Owner` | ownership_change |
| plan review | `Transaction` contains `MFDV` or `Hot Dog` | mobile |
| plan review | `Transaction` contains `SEAT`, `NOST`, `COMBO)` or ends in `Initial Plan Review` | new |
| plan review | `Transaction` contains `Request Plan Review`, or `Type of Facility (Rank)` = `Catering` | ignored |

Rows outside `COUNTIES` are counted in `rows_fetched` but never stored. `rows_new` = new in-county raw records.

**`weekly_w1/`** (6 rows: 5 in `newfood.csv`, 1 in `chgownr_food.csv`):

| # | File | Business Name | Licensee Name | Location Street Address | City | ZIP | County | Rank | Licence No. | Approval date | Primary phone |
|---|---|---|---|---|---|---|---|---|---|---|---|
| W1-1 | newfood | SALT & SMOKE BBQ | SALT & SMOKE BBQ LLC | 1450 N HARBOR CITY BLVD | MELBOURNE | 32935 | Brevard | SEAT | SEA1590001 | 09/22/2026 | 321-555-0101 |
| W1-2 | newfood | COASTAL TACOS | COASTAL TACOS INC | 210 W COCOA BEACH CSWY | COCOA BEACH | 32931 | Brevard | NOST | NOS1590002 | 09/23/2026 | 321-555-0102 |
| W1-3 | chgownr | THE ROCKET DINER | ROCKET DINER HOLDINGS LLC | 3500 S WASHINGTON AVE | TITUSVILLE | 32780 | Brevard | SEAT | SEA1590003 | 09/24/2026 | 321-555-0103 |
| W1-4 | newfood | SPACECOAST WAFFLES | SPACECOAST WAFFLES LLC | 1100 MALABAR RD SE | PALM BAY | 32907 | Brevard | MFDV | MFD1590004 | 09/25/2026 | 321-555-0104 |
| W1-5 | newfood | HARBOR VENDING CO | HARBOR VENDING CO | 100 E NEW HAVEN AVE | MELBOURNE | 32901 | Brevard | VEND | VEN1590005 | 09/21/2026 | |
| W1-6 | newfood | LAKE EOLA RAMEN | LAKE EOLA RAMEN LLC | 50 E CENTRAL BLVD | ORLANDO | 32801 | Orange | SEAT | SEA5890006 | 09/22/2026 | 407-555-0106 |

**`weekly_w2/`** (3 rows, all in `newfood.csv`; `chgownr_food.csv` is header-only):

| # | Business Name | Licensee Name | Location Street Address | City | ZIP | County | Rank | Licence No. | Approval date | Primary phone |
|---|---|---|---|---|---|---|---|---|---|---|
| W2-1 | INDIAN RIVER PHO | INDIAN RIVER PHO LLC | 2235 N COURTENAY PKWY | MERRITT ISLAND | 32953 | Brevard | SEAT | SEA1590007 | 09/29/2026 | 321-555-0201 |
| W2-2 | COCOA VILLAGE CREPERIE | COCOA VILLAGE CREPERIE LLC | 401 DELANNOY AVE | COCOA | 32922 | Brevard | NOST | NOS1590008 | 09/30/2026 | 321-555-0202 |
| W2-3 | SPACE COAST CATERING | SPACE COAST CATERING LLC | 77 CLEARLAKE RD | COCOA | 32922 | Brevard | CATR | CAT1590009 | 09/28/2026 | |

**`plan_review_0901.csv`** (3 rows, all Brevard, `Plan Review Status Plan` = `In process`, `License Number ` empty):

| # | Business (DBA) Name | Facility Location Address | City | ZIP | Review Application Date | Transaction | Facility Phone | Facility Email | Mailing Name |
|---|---|---|---|---|---|---|---|---|---|
| P-1 | Indian River Pho LLC | 2235 N. Courtenay Parkway | MERRITT ISLAND | 32953 | 09/01/2026 | 1034/Plan Review and Initial (COMBO SEAT) | 321-555-0301 | owner@indianriverpho.example | INDIAN RIVER PHO LLC |
| P-2 | BANANA RIVER BAGELS | 1980 N Atlantic Ave Suite 101 | COCOA BEACH | 32931 | 09/01/2026 | 1031/Initial Plan Review (NOST) | 321-555-0302 | bagels@example.com | BANANA RIVER BAGELS LLC |
| P-3 | VIERA NOODLE BAR | 7720 N WICKHAM RD | MELBOURNE | 32940 | 09/01/2026 | 1030/Initial Plan Review (SEAT) | 321-555-0303 | | VIERA NOODLE BAR INC |

P-1 and W2-1 differ in suffix (`LLC`), punctuation (`N.`), street type (`Parkway`/`Pkwy`) and case, and P-1 has no licence number. The matcher must still merge them by `lead_key`.

**Other fixtures:**

| Fixture | Content | Used by |
|---|---|---|
| `plan_review_1006.csv` | P-1 again, but `Review Application Date` 10/06/2026 (a resubmitted plan) | E2E-09 |
| `weekly_partial_error/` | `newfood.csv` = `weekly_w1`'s. Fetching `chgownr_food.csv` raises `FetchError("chgownr_food.csv: HTTP 500")` | E2E-10 |
| `plan_review_with_licence.csv` | One row: DBA `SALTY BAGEL CAFE`, address `223 W HIBISCUS BLVD`, ZIP 32901, `License Number ` `1590010`, application date 08/01/2026, Transaction `1034/Plan Review and Initial (COMBO SEAT)` | E2E-09b |
| `weekly_licence_match/` | `newfood.csv` with one row: `SALTY BAGEL`, `223 W HIBISCUSS BLVD` (misspelt, as in real DBPR data), ZIP 32901, SEAT, `SEA1590010`, approved 09/15/2026 | E2E-09b |
| `weekly_empty/` | Both files with the real header and zero data rows | E2E-26 |
| `weekly_bad_columns/` | `weekly_w1` with the `Location County` header in `newfood.csv` renamed to `CNTY_RENAMED` | E2E-27 |
| `weekly_unavailable/` | Fetching `newfood.csv` raises `FetchError("newfood.csv: HTTP 503")` | E2E-25 |
| `weekly_real_sample/`, `plan_review_real_sample.csv` | Trimmed real captures from 2026-10-03: every Brevard row plus 10 Orange rows | E2E-06, E2E-11 |

`FixtureFetcher` raises a fixture's configured error from a small manifest, `fixtures/errors.json` (`{"weekly_unavailable": {"newfood.csv": "newfood.csv: HTTP 503"}, ...}`), so failure paths go through the same code as real HTTP errors.

**Standard dataset.** The helper `seed_standard(api)` does three things:

1. Clock `2026-09-01T12:00:00Z`, then run `import-plan-review` with `plan_review_0901.csv`.
2. Clock `2026-09-28T12:00:00Z`, then run `import-weekly` with `weekly_w1`.
3. Leave the clock at `2026-09-28T12:00:00Z`.

It produces exactly these 7 leads:

| Lead | lead_type | stage | first_seen | licensed_on | days_ahead | phone | email |
|---|---|---|---|---|---|---|---|
| Banana River Bagels | new | Applied | 2026-09-01 | | | 321-555-0302 | bagels@example.com |
| Indian River Pho | new | Applied | 2026-09-01 | | | 321-555-0301 | owner@indianriverpho.example |
| Viera Noodle Bar | new | Applied | 2026-09-01 | | | 321-555-0303 | |
| Salt & Smoke BBQ | new | Licensed | 2026-09-22 | 2026-09-22 | 0 | 321-555-0101 | |
| Coastal Tacos | new | Licensed | 2026-09-23 | 2026-09-23 | 0 | 321-555-0102 | |
| The Rocket Diner | ownership_change | Licensed | 2026-09-24 | 2026-09-24 | 0 | 321-555-0103 | |
| Spacecoast Waffles | mobile | Licensed | 2026-09-25 | 2026-09-25 | 0 | 321-555-0104 | |

`seed_plus_w2(api)` = the standard dataset, then clock `2026-10-05T10:00:00Z` and `import-weekly` with `weekly_w2`. That makes 8 leads:

- Indian River Pho becomes Licensed: licensed_on 2026-09-29, days_ahead 28. Its phone becomes 321-555-0201, the newest non-empty value. Its email stays owner@indianriverpho.example, because the licence row has none.
- Cocoa Village Creperie is added: new, Licensed, 2026-09-30, 0.

**Name display:** `business_name` comes from the most recent record, unless the operator set a display name (L5). Assertions on names use case-insensitive substring matches, after HTML-unescaping when checking email HTML. So "Indian River Pho" matches "INDIAN RIVER PHO", and "Salt & Smoke BBQ" matches "SALT &amp; SMOKE BBQ".

### 1.5 Fixed formats

| Thing | Exact format |
|---|---|
| CSV header (web, CLI, digest attachment) | `business_name,address,city,zip,county,lead_type,stage,first_seen,licensed_on,days_ahead,licensee,phone,email` |
| CSV values | `lead_type` ∈ `new`, `ownership_change`, `mobile`. `stage` ∈ `Applied`, `Licensed`. Dates are ISO. `days_ahead` and `licensed_on` are empty until licensed. Rows are sorted by `first_seen` descending, then `business_name` ascending |
| Web export filename | `leads-YYYY-MM-DD.csv` (date = today in ET from the clock) |
| Weekly digest subject | `{n} new restaurant(s) in {Counties} - week of {Mon D, YYYY}`, for example `3 new restaurants in Brevard - week of Sep 7, 2026`, or `1 new restaurant in Brevard - week of Sep 7, 2026` |
| Daily digest subject | `{n} new restaurant(s) in {Counties} - {Mon D, YYYY}` |
| Test digest subject | `[TEST] ` + the subject the real digest would have |
| Empty digest body | Contains `No new restaurants this week` (weekly) or `No new restaurants today` (daily) |
| Digest lead stage label | `Application in progress` for Applied. `Licensed {Mon D, YYYY}` for Licensed |
| Digest lead block | Name, type label, stage label, address, city, ZIP, then `Phone: {phone}` and `Email: {email}` lines (each omitted when empty) |
| Lead type labels (UI and digest) | `New`, `Ownership change`, `Food truck` |
| Digest attachment | `leads-YYYY-MM-DD.csv` (send date in ET), the same columns as above, only that digest's leads |
| Digest footer | An unsubscribe link `{APP_BASE_URL}/unsubscribe/{token}` and the exact `OPERATOR_POSTAL_ADDRESS` text |
| Alert subject | `[OpeningSoon FL] Source problem: {source} - {reason}`, where source ∈ `dbpr_weekly`, `dbpr_plan_review` and reason ∈ `run failed`, `zero rows`, `columns changed`, `stale` |
| Days-ahead label (UI) | `28 days ahead`, `0 days ahead`, or `—` when not licensed |
| CLI output | ASCII only (the Windows console is cp1252). Export prints `Exported {n} leads to {path}` |

**Health status:** red = the last run failed, returned zero rows while the 4-week average was above 0, or saw changed columns. Amber = the last successful run is older than 8 days (`dbpr_weekly`) or 36 hours (`dbpr_plan_review`). Otherwise green. A source with no runs at all is amber.

**Schedule (ET):** `import-plan-review` daily 05:00. `import-weekly` daily 06:00, because DBPR's update day isn't fixed and imports are idempotent. `send-digests-daily` daily 07:00. `send-digests-weekly` Monday 07:00. `check-health` hourly at :15.

### 1.6 Selector contract (`data-testid`)

| testid | Element |
|---|---|
| `login-password` / `login-submit` / `login-error` | Login form and its error line |
| `nav-dashboard` / `nav-leads` / `nav-vendors` / `nav-sources` / `logout` | Top navigation |
| `stat-new-this-week` / `stat-applied` / `stat-active-vendors` | Dashboard numbers (text is the number only) |
| `source-last-run` | Dashboard row per source (multiple). Has `data-source` and `data-status` |
| `leads-table` / `leads-count` / `leads-empty` | Leads table, `"{n} leads"` text, empty state |
| `lead-row` | Each row (multiple). Has `data-lead-id` |
| `lead-name` / `lead-stage` / `lead-type` / `lead-days-ahead` / `lead-first-seen` | Cells inside `lead-row` |
| `filter-stage` | Select: `All`, `Applied`, `Licensed` |
| `filter-type` | Select: `All`, `New`, `Ownership change`, `Food truck` |
| `filter-county` / `filter-from` / `filter-to` / `filter-search` / `filter-hidden` | County select, date inputs, search box, "Show hidden" checkbox |
| `filter-apply` / `export-csv` | Apply filters. Download CSV of the current filter |
| `lead-detail-name` / `lead-detail-stage` / `lead-detail-type` / `lead-detail-days-ahead` | Lead page header |
| `lead-detail-phone` / `lead-detail-email` / `lead-detail-licensee` | Contact panel on the lead page (`—` when empty) |
| `timeline-event` | Each event (multiple, oldest first). Has `data-stage` and `data-date` |
| `raw-record` | Each source record block (multiple). Has `data-source` |
| `lead-hide` / `lead-unhide` / `lead-edit-name` / `lead-note-input` / `lead-save` | L5 controls |
| `vendor-new` / `vendor-row` | New vendor button. Each vendor row (multiple, has `data-vendor-id`) |
| `vendor-name` / `vendor-emails` / `vendor-category` / `vendor-cadence` / `vendor-active` | Vendor form. Emails are comma-separated |
| `vendor-county-brevard` / `vendor-county-orange` / `vendor-county-volusia` | County checkboxes |
| `vendor-save` / `vendor-error` / `vendor-cap-warning` / `vendor-status` | Save, validation error, V3 warning, `Active` or `Inactive` cell in `vendor-row` |
| `digest-preview-link` / `digest-preview` / `digest-send-test` / `digest-test-sent` | Preview link on the vendor row, preview container, test-send button, confirmation text |
| `source-row` | Each source on `/sources` (multiple). Has `data-source` and `data-status` |
| `run-row` | Each recent run under a source (multiple) |
| `source-upload-file` / `source-upload-submit` / `upload-result` | I7 manual upload |
| `unsubscribe-confirm` | Unsubscribe confirmation text |

Helpers: `login(page)` fills `login-password` with `test-admin-pw` and submits. `api` is a small httpx client for the `/test/*` routes.

## 2. Scenarios

Each scenario starts from `POST /test/reset` and runs against the test server. "Run X with F" means `POST /test/run/X {"fixture": "F"}`. "Clock T" means `POST /test/clock {"now": T}`.

### Stage 0 — Skeleton

**E2E-00 @stage0 app boots.** `GET /health` → 200 `{"status": "ok", "db": "ok"}`. `POST /test/reset` → 200 `{"ok": true}`. `GET /login` shows `login-password`.

**E2E-01 @stage0 env validation (Configuration).** Run `start_app` with `ADMIN_PASSWORD` unset on port 8011. The process exits non-zero within 15 s, and its combined output contains `ADMIN_PASSWORD`.

**E2E-02 @stage0 test routes are gated (Security).** Run `start_app` with `TEST_ROUTES=0` on port 8012. `POST /test/reset` → 404, and `GET /health` → 200.

### Stage 1 — Weekly import + lead sheet

**E2E-03 @stage1 weekly import creates leads (I1, I3, L1, L7).** Clock `2026-09-28T12:00:00Z`. Run `import-weekly` with `weekly_w1`.
- The response has `status: "ok"`, `rows_fetched: 6`, `rows_new: 5` and `leads_created: 4`.
- `/test/leads` has exactly 4 leads: SALT & SMOKE BBQ (new), COASTAL TACOS (new), THE ROCKET DINER (`ownership_change`) and SPACECOAST WAFFLES (`mobile`). All are Licensed, with `days_ahead` 0, county Brevard, and the phone from their row.
- Neither HARBOR VENDING CO (VEND) nor LAKE EOLA RAMEN (Orange) is a lead.
- `/test/state.raw_records` = 5, because the Orange row isn't stored. `/test/runs[0]` has `source: "dbpr_weekly"` and `status: "ok"`.

**E2E-04 @stage1 import is idempotent (I2).** Run `import-weekly` with `weekly_w1` twice. The second response has `rows_new: 0` and `leads_created: 0`. Afterwards `/test/state` shows `leads` 4, `raw_records` 5 and `source_runs` 2.

**E2E-05 @stage1 CLI lead sheet (E4, U1).** With the test `DATABASE_URL`, run `uv run osfl import-weekly --county brevard --dir fixtures/dbpr_weekly/weekly_w1` (exit 0). Then run `uv run osfl export-csv --county brevard --since 2026-09-01 --out <tmp>/leads.csv`.
- Exit code 0, and stdout is `Exported 4 leads to <path>`.
- The file's first line equals the CSV header in §1.5 exactly.
- It has 4 data rows, the first being SPACECOAST WAFFLES (latest `first_seen`).
- The SALT & SMOKE BBQ row has `lead_type` `new`, `stage` `Licensed`, `first_seen` `2026-09-22`, `licensed_on` `2026-09-22`, `days_ahead` `0`, `licensee` `SALT & SMOKE BBQ LLC`, `phone` `321-555-0101` and an empty `email`.

**E2E-06 @stage1 real sample parses (I1).** Run `import-weekly` with `weekly_real_sample`.
- The response has `status: "ok"`, `rows_fetched` ≥ 20 and `error: null`.
- Every lead in `/test/leads` has county Brevard, and none has an empty `business_name` or `address`.
- At least one lead has each `lead_type`: `new`, `ownership_change` and `mobile`.

### Stage 2 — Plan review import + merge

**E2E-07 @stage2 plan reviews become Applied leads (I4, L7, U2).** Clock `2026-09-01T12:00:00Z`. Run `import-plan-review` with `plan_review_0901.csv`. The response has `leads_created: 3`.
- All three leads (Banana River Bagels, Indian River Pho, Viera Noodle Bar) are `Applied`, with `first_seen` `2026-09-01`, `days_ahead` `null`, and one event each with `source: "dbpr_plan_review"`.
- Banana River Bagels has `phone` `321-555-0302` and `email` `bagels@example.com`.
- Viera Noodle Bar has an empty `email`.

**E2E-08 @stage2 plan review + licence merge into one lead (L2, L3, L4, L7).** Run `seed_plus_w2`.
- `/test/leads` has 8 leads and exactly one whose name matches `indian river pho`.
- That lead has `stage` `Licensed`, `first_seen` `2026-09-01`, `licensed_on` `2026-09-29`, `days_ahead` `28`, `phone` `321-555-0201` and `email` `owner@indianriverpho.example`.
- Its `events` are `[{stage: "Applied", date: "2026-09-01", source: "dbpr_plan_review"}, {stage: "Licensed", date: "2026-09-29", source: "dbpr_weekly"}]`.

**E2E-09 @stage2 stage never regresses, first_seen never moves later (L3).** Clock `2026-10-05T10:00:00Z`, then run `import-weekly` with `weekly_w2`. Clock `2026-10-06T12:00:00Z`, then run `import-plan-review` with `plan_review_1006.csv`.
- Indian River Pho has `stage` `Licensed`, `first_seen` `2026-09-29` and `days_ahead` `0`.
- It has 2 events, the second being `Applied` dated `2026-10-06`.
- The lead count is 2 (Indian River Pho, Cocoa Village Creperie).

**E2E-09b @stage2 licence-number match beats a misspelt address (L2).** Clock `2026-08-01T12:00:00Z`, then run `import-plan-review` with `plan_review_with_licence.csv`. Clock `2026-09-16T12:00:00Z`, then run `import-weekly` with `weekly_licence_match`. `/test/leads` has exactly 1 lead, with 2 events, `stage` `Licensed`, `first_seen` `2026-08-01`, `licensed_on` `2026-09-15` and `days_ahead` `45`.

**E2E-10 @stage2 a failed run is atomic (Reliability, H1).** Clock `2026-09-28T12:00:00Z`. Run `import-weekly` with `weekly_partial_error`.
- The response has `status: "failed"`, `leads_created: 0`, and an `error` containing `chgownr_food.csv`.
- `/test/state` shows `leads` 0 and `raw_records` 0, even though `newfood.csv` was fetched and parsed.
- `/test/runs[0]` has `status: "failed"`.

**E2E-11 @stage2 real plan-review sample parses (I4).** Run `import-plan-review` with `plan_review_real_sample.csv`.
- The response has `status: "ok"` and `error: null`.
- There are at least 50 leads, all with county Brevard, stage `Applied`, and a non-empty name, address and ZIP.
- At least 80% have a phone or an email.

### Stage 3 — Admin console

**E2E-12 @stage3 login (A1).**
- Visiting `/leads` without a session redirects to `/login`.
- Submitting the password `wrong` shows `login-error` with the text `Wrong password`.
- Submitting `test-admin-pw` lands on the dashboard (`stat-new-this-week` visible).
- Clicking `logout`, then visiting `/leads`, redirects to `/login` again.

**E2E-13 @stage3 dashboard (A4).** Run `seed_standard`. After login:
- `stat-new-this-week` = `4` (leads with `first_seen` in the 7 days up to now), `stat-applied` = `3`, `stat-active-vendors` = `0`.
- There's a `source-last-run` row for each source. `dbpr_weekly` has `data-status` `green`. `dbpr_plan_review` has `data-status` `amber`, because its last run on 2026-09-01 is older than 36 hours.

**E2E-14 @stage3 leads table, filters, search and persistence (A2, U2).** Run `seed_standard`, then log in and open `nav-leads`.
- `leads-count` = `7 leads`. The default order is `first_seen` descending, so the first row is Spacecoast Waffles.
- Set `filter-stage` = `Applied` and apply. There are 3 rows: Banana River Bagels, Indian River Pho and Viera Noodle Bar. Each row's `lead-days-ahead` shows `—`.
- **Reload the page:** the filter is still applied (it's in the URL query) and there are still 3 rows.
- Set `filter-stage` = `All` and `filter-type` = `Ownership change`. There's 1 row, The Rocket Diner.
- Reset the filters and search `bagel`. There's 1 row.
- Search `zzz`. `leads-empty` is visible.

**E2E-15 @stage3 lead detail and timeline (A3, U3).** Run `seed_plus_w2`, then log in and open the Indian River Pho row.
- `lead-detail-stage` = `Licensed` and `lead-detail-days-ahead` = `28 days ahead`.
- Two `timeline-event`s appear in order: (`Applied`, `2026-09-01`) and (`Licensed`, `2026-09-29`).
- Two `raw-record`s appear, with `data-source` `dbpr_plan_review` and `dbpr_weekly`. The plan-review one shows the text `2235 N. Courtenay Parkway`.
- `lead-detail-phone` = `321-555-0201`, `lead-detail-email` = `owner@indianriverpho.example` and `lead-detail-licensee` = `INDIAN RIVER PHO LLC`.

**E2E-16 @stage3 vendor management (V1, V2, U4).** Log in and open `nav-vendors`.
- The `vendor-category` options are exactly `POS`, `Equipment`, `Insurance`, `Payroll`, `Pest control`, `Food supply` and `Other`.
- Saving the email `not-an-email` shows `vendor-error` with the text `Enter valid email addresses`, and no vendor is created.
- Create `Space Coast POS`: emails `pos@example.com`, POS, `vendor-county-brevard`, weekly, active. One `vendor-row` appears with `vendor-status` `Active`.
- Edit its cadence to daily and save. **Reload:** the cadence is still daily.
- Untick `vendor-active` and save. `vendor-status` = `Inactive`, and the dashboard shows `stat-active-vendors` = `0`.

**E2E-17 @stage3 web CSV export (E4).** Run `seed_standard`, then log in. Filter `Applied` and click `export-csv`.
- The download is named `leads-2026-09-28.csv`.
- Line 1 equals the §1.5 header.
- It has exactly 3 data rows, all with `stage` `Applied` and an empty `days_ahead`.

**E2E-18 @stage3 hide, rename, note (L5).** Run `seed_standard`, then log in and open Viera Noodle Bar.
- Set `lead-edit-name` to `Viera Noodle Bar & Grill` and `lead-note-input` to `Owner is Sam, opening Nov`, then click `lead-save`. **Reload:** both values persist.
- Click `lead-hide`. Back on the leads list, `leads-count` = `6 leads`. Ticking `filter-hidden` shows 7.
- A later re-import of `plan_review_0901.csv` (clock `2026-09-02T12:00:00Z`) keeps the custom name and the hidden flag.

### Stage 4 — Digests

**E2E-19 @stage4 ★ MOST IMPORTANT — a vendor hears about a restaurant while it's still applying, and never twice (E1, E3, E4, L4, U7).**

1. Clock `2026-09-01T12:00:00Z`, then run `import-plan-review` with `plan_review_0901.csv`.
2. Log in and create vendor `Space Coast POS` (pos@example.com, POS, Brevard, weekly, active) through the UI.
3. Clock `2026-09-07T11:00:00Z` (Monday 07:00 ET), then run `send-digests-weekly`. The response has `emails_sent: 1`.
4. `/test/outbox` has exactly 1 email:
   - `to` = `["pos@example.com"]`.
   - `subject` = `3 new restaurants in Brevard - week of Sep 7, 2026`.
   - `html` contains `Banana River Bagels`, `Indian River Pho` and `Viera Noodle Bar`, and `Application in progress` 3 times.
   - `html` contains `Phone: 321-555-0302` and `Email: bagels@example.com`.
   - There's one attachment, `leads-2026-09-07.csv`, with the §1.5 header and 3 rows, all `Applied`.
5. Clock `2026-09-28T12:00:00Z` and run `import-weekly` with `weekly_w1`. Then clock `2026-10-05T10:00:00Z` and run `import-weekly` with `weekly_w2`.
6. Clock `2026-10-05T11:00:00Z`, then run `send-digests-weekly`. That's 1 new email (2 in total). The second email:
   - `subject` = `5 new restaurants in Brevard - week of Oct 5, 2026`.
   - `html` contains Salt & Smoke BBQ, Coastal Tacos, The Rocket Diner, Spacecoast Waffles and Cocoa Village Creperie. It also contains `Ownership change` and `Food truck`, and **does not contain** `Indian River Pho`.
7. `/test/deliveries` shows Indian River Pho delivered to Space Coast POS on `2026-09-07`. `/test/leads` shows its `licensed_on` `2026-09-29` and `days_ahead` `28`. So the vendor heard 22 days before the licence was issued.

If this test passes, the business works: early, restaurant-specific, no duplicates.

**E2E-20 @stage4 one digest per period (E3).** Do steps 1–3 of E2E-19, then run `send-digests-weekly` again at the same clock. The response has `emails_sent: 0`. `/test/state` shows `outbox` 1 and `deliveries` 3.

**E2E-21 @stage4 cadence, region, inactive, hidden and empty digests (E1, E2, E6, V1).** Run `seed_standard`. Hide The Rocket Diner via the UI. Create these vendors through the UI:

| Vendor | Email | Category | Counties | Cadence | Active |
|---|---|---|---|---|---|
| Space Coast POS | pos@example.com | POS | Brevard | weekly | yes |
| Brevard Pest Pros | pest@example.com | Pest control | Brevard | daily | yes |
| Orlando Insurance Group | ins@example.com | Insurance | Orange | weekly | yes |
| Idle Equipment Co | idle@example.com | Equipment | Brevard | weekly | no |

- Clock `2026-09-29T11:00:00Z`, then run `send-digests-daily`. The response has `emails_sent: 1`, going to `pest@example.com` with the subject `6 new restaurants in Brevard - Sep 29, 2026`. The email doesn't contain `Rocket Diner`.
- Clock `2026-10-05T11:00:00Z`, then run `send-digests-weekly`. The response has `emails_sent: 2`.
  - `pos@example.com` gets `6 new restaurants in Brevard - week of Oct 5, 2026`.
  - `ins@example.com` gets `0 new restaurants in Orange - week of Oct 5, 2026`, whose `html` contains `No new restaurants this week`.
  - Nothing goes to `idle@example.com`.

**E2E-22 @stage4 preview and test send (E5, U5).** Run `seed_standard`, then create Space Coast POS (as in E2E-19).
- Clicking its `digest-preview-link` shows `digest-preview` containing all 7 lead names.
- Clicking `digest-send-test` shows `digest-test-sent` with the text `Test sent to operator@example.com`.
- The outbox has 1 email to `["operator@example.com"]` with the subject `[TEST] 7 new restaurants in Brevard - week of Sep 28, 2026`.
- `/test/state.deliveries` = 0, because a test send marks nothing delivered.
- Run `send-digests-weekly` without changing the clock. The vendor's real email still lists all 7.

**E2E-23 @stage4 unsubscribe and postal address (E7).** Do steps 1–3 of E2E-19.
- The email `html` contains `OpeningSoon FL, PO Box 1000, Melbourne, FL 32901`, and a link matching `http://127.0.0.1:8001/unsubscribe/[A-Za-z0-9_-]{16,}`.
- Opening that link in the browser shows `unsubscribe-confirm` with the text `You're unsubscribed from OpeningSoon FL digests.`
- On the vendors page, Space Coast POS has `vendor-status` `Inactive`.
- Clock `2026-09-14T11:00:00Z` and run `send-digests-weekly`. The response has `emails_sent: 0`.
- Opening the link a second time shows the same confirmation, with no error.

**E2E-24 @stage4 category cap warning (V3).** With `MAX_VENDORS_PER_CATEGORY=2`, create three active POS vendors for Brevard. The first two save with no `vendor-cap-warning`. The third saves (it's listed and active), and `vendor-cap-warning` reads `POS already has 2 active vendors in Brevard`.

### Stage 5 — Source health, schedule, deploy

**E2E-25 @stage5 failed run alerts (H1, H2, U6).** Clock `2026-09-28T12:00:00Z`. Run `import-weekly` with `weekly_unavailable`.
- The response has `status: "failed"` and an `error` containing `HTTP 503`.
- The outbox has 1 email to `["operator@example.com"]` with the subject `[OpeningSoon FL] Source problem: dbpr_weekly - run failed`, whose `text` contains `HTTP 503`.
- On `/sources` (after login), the `source-row[data-source=dbpr_weekly]` has `data-status` `red`.

**E2E-26 @stage5 zero rows alerts (H2).** Clock `2026-09-28T12:00:00Z` and run `import-weekly` with `weekly_w1`. Then clock `2026-10-05T12:00:00Z` and run `import-weekly` with `weekly_empty`.
- The second response has `status: "ok"` and `rows_fetched: 0`.
- The outbox has 1 email with the subject `[OpeningSoon FL] Source problem: dbpr_weekly - zero rows`.
- The source row is `red`.

**E2E-27 @stage5 changed columns alert (H2).** Run `import-weekly` with `weekly_bad_columns`.
- The response has `status: "failed"` and an `error` containing `CNTY_RENAMED`.
- `leads_created` = 0.
- The outbox subject is `[OpeningSoon FL] Source problem: dbpr_weekly - columns changed`.

**E2E-28 @stage5 staleness and run history (H3).** Clock `2026-09-28T12:00:00Z` and run `import-weekly` with `weekly_w1` 12 times. Clock `2026-09-29T12:00:00Z` and run `import-plan-review` with `plan_review_0901.csv`. After login, on `/sources`:
- `dbpr_weekly` is `green` and shows exactly 10 `run-row`s.
- Clock `2026-10-06T12:00:00Z` and run `check-health`. `dbpr_weekly` is still `green` (exactly 8 days old), `dbpr_plan_review` is `amber`, and `alerts_sent: 1` with the subject `[OpeningSoon FL] Source problem: dbpr_plan_review - stale`.
- Clock `2026-10-07T12:00:00Z` and run `check-health`. `dbpr_weekly` is `amber`, and `alerts_sent: 1` (only the newly stale source). A third `check-health` at the same clock gives `alerts_sent: 0`.

**E2E-29 @stage5 manual upload fallback (I7).** Log in and open `/sources`. Upload `fixtures/dbpr_weekly/weekly_w1/newfood.csv` through `source-upload-file` and click `source-upload-submit`.
- `upload-result` reads `5 rows, 3 new leads` (newfood only: SALT & SMOKE BBQ, COASTAL TACOS, SPACECOAST WAFFLES).
- `/test/runs[0]` has `source: "dbpr_weekly"` and `trigger: "manual"`.

**E2E-30 @stage5 schedule wiring (E1, E2, Scheduling).** Clock `2026-10-05T09:30:00Z` (Monday 05:30 ET). `/test/schedule` returns:
- `import-weekly` → `2026-10-05T10:00:00Z`
- `import-plan-review` → `2026-10-06T09:00:00Z`
- `send-digests-daily` → `2026-10-05T11:00:00Z`
- `send-digests-weekly` → `2026-10-05T11:00:00Z`
- `check-health` → `2026-10-05T10:15:00Z` (06:15 ET; corrected 2026-10-03, DECISIONS D7)

Clock `2026-10-06T12:00:00Z`. `send-digests-weekly` → `2026-10-12T11:00:00Z`.

## 3. Smoke suite — live DBPR (manual only)

These are skipped unless `RUN_SMOKE=1`. They run against a dev server with `SOURCE_MODE=live`, with no reset between steps. Assertions are loose. Each one stays polite (I5): at most 3 file downloads per run.

**SMOKE-1 @smoke live licence import.** `uv run osfl import-weekly --county brevard` → exit 0. The latest `source_runs` row has `status` `ok` and `rows_fetched` > 0, and at least one Brevard raw record is stored.

**SMOKE-2 @smoke live headers unchanged.** The live headers of `newfood.csv`, `chgownr_food.csv` and `HR_plan_review.csv` equal those in `fixtures/headers/`.

**SMOKE-3 @smoke live plan-review import.** `uv run osfl import-plan-review --county brevard` → exit 0, with `status` `ok` and at least one Brevard lead in stage Applied.

**SMOKE-4 @smoke real email.** This runs only if `RESEND_API_KEY` and `EMAIL_FROM` are set. With `EMAIL_MODE=resend`, a test digest sent to `OPERATOR_EMAIL` returns a Resend message id.

## 4. Required unit tests (`tests/`)

| ID | Function | Cases |
|---|---|---|
| UT-01 | `normalise_name` | `Indian River Pho LLC` → `INDIAN RIVER PHO`. `Salt & Smoke BBQ, L.L.C.` → `SALT AND SMOKE BBQ`. `Coastal Tacos Inc` → `COASTAL TACOS` |
| UT-02 | `normalise_address` | `2235 N. Courtenay Parkway` → `2235 N COURTENAY PKWY`. `1980 N Atlantic Ave Suite 101` → `1980 N ATLANTIC AVE STE 101`. `210 West Cocoa Beach Causeway` → `210 W COCOA BEACH CSWY` |
| UT-03 | `lead_key` | P-1 and W2-1 give the same key. W1-1 and the same row with ZIP 32901 give different keys |
| UT-09 | `licence_digits` | `SEA1590010` → `1590010`. `1590010` → `1590010`. Empty → `None`. The matcher prefers a licence-digit match over `lead_key` |
| UT-04 | `classify` | W1-1…W1-6 → new, new, ownership_change, mobile, ignored (VEND), new (the county filter is separate). W2-3 → ignored (CATR). Plan-review transactions: `1034/Plan Review and Initial (COMBO SEAT)` → new. `1034/Plan Review and Initial (COMBO)` → new. `1030/Initial Plan Review` → new. `1036/Plan Review and Initial (COMBO MFDV)` → mobile. `1030/Initial Hot Dog Plan Review` → mobile. `3021/Request to Change Owner (MFDV)` → ownership_change. `3027/Request Plan Review` → ignored |
| UT-05 | Live fetcher politeness | With a fake transport and a fake sleep: requests are spaced ≥ `FETCH_MIN_INTERVAL_S`, the `User-Agent` equals `FETCH_USER_AGENT`, and a 500 is retried 3 times with growing delays, then raises `FetchError` |
| UT-06 | `digest_period` | `2026-09-07T11:00Z` weekly → `2026-W37`. `2026-09-13T23:59-04:00` weekly → `2026-W37`. Daily `2026-09-29T03:59Z` → `2026-09-28` (still the 28th in ET) |
| UT-07 | `health_status` | The red, amber and green rules in §1.5, including "no runs → amber" and "exactly 8 days → green" |
| UT-08 | `days_ahead` | Applied 2026-09-01 + Licensed 2026-09-29 → 28. Licensed only → 0. Applied only → `None` |

## 5. Playwright MCP walkthrough

After a stage's specs pass, walk the same scenario ids through the `playwright-headless` MCP server. It's an independent browser driven step by step.

1. Start a **separate walkthrough server** on `127.0.0.1:8002` with `DATABASE_URL` = `WALK_DATABASE_URL` (database `osfl_walk`) and the test env otherwise. Start it from the venv's Python and log to `logs/walk.log`. Never run the walkthrough while pytest is running: a pytest reset would wipe the walkthrough's data.
2. For each scenario:
   - Call `POST /test/reset` and the seed helpers' `/test/*` calls with curl or httpx.
   - Navigate with `browser_navigate`, then `browser_snapshot`.
   - Do the steps with the `data-testid` selectors (`browser_click`, `browser_type`, `browser_select_option`, `browser_file_upload`), and snapshot after each key step.
3. Check the same outcomes the spec asserts. For emails, read `GET /test/outbox`. For E2E-23, follow the unsubscribe link with `browser_navigate`.
4. Chain the stage's scenarios the way the operator would use them, for example: seed → login → filter → open lead → create vendor → preview. Take one `browser_take_screenshot` of the leads table and the lead detail page per stage from stage 3 on.
5. Record `E2E-xx: pass | fail — note` in `docs/VERIFICATION.md`. From stage 4 on, walk **E2E-19 every time**.

A scenario that passes in pytest but fails in the walkthrough, or the reverse, is a bug in the spec or the app. Investigate and fix it. Never mark it passed.
