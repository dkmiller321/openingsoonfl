# DECISIONS.md — decision log

Claude Code appends one entry per decision it makes without asking: date, decision, why, and alternatives considered. The stage 0 capture spike records here the real DBPR weekly file URL and columns, the licence-search URL and flow, and how each canonical fixture field (for example "change of ownership") maps onto the real format. Anything put out of scope instead of implemented is also recorded here.

## Log

### D1 · 2026-10-03 · DBPR sources found in the stage 0 spike
- Download page: https://www2.myfloridalicense.com/hotels-restaurants/public-records/ (all files statewide CSV, `last-modified` Sat 2026-10-03 ~10:48 UTC, so likely refreshed weekly on Saturdays).
- Licences (`dbpr_weekly`): `newfood.csv` (new licences, current fiscal year from 07/01, 1,673 rows statewide, 39 Brevard) and `chgownr_food.csv` (owner changes, 1,484 rows, 43 Brevard). Both share one 38-column header; key columns: `Application Type`, `Application Approval Date ` (trailing space), `Licensee Name`, `Rank Code` (SEAT, NOST, MFDV, HTDG, CATR, VEND), `Business Name`, `Location Street Address`, `Location City`, `Location Zip Code`, `Location County` (name, e.g. `Brevard`), `Primary Phone Number`, `License Number` (e.g. `SEA1507428`), `Number of Seats`, `District` (Brevard = D4).
- Plan reviews (`dbpr_plan_review`): `HR_plan_review.csv` (11,319 rows statewide since 2025-04, 277 Brevard). Key columns: `County`, `Business (Does Business As – DBA) Name` (the dash is a UTF-8 en dash; read every DBPR file as UTF-8 with `utf-8-sig` and `errors="replace"`), `Facility Location Address/City/Zip Code`, `Facility Phone Number`, `Facility Email Address`, `Plan Review Status Plan` (In process, Approved, Approved with Provisos, Incomplete, blank), `Review Application Date`, `Transaction` (e.g. `1034/Plan Review and Initial (COMBO SEAT)`), `License Number ` (trailing space; digits only, often blank), `Mailing Name`, `Contact Phone Number`, `Contact Email Address`.
- Evidence the plan-review file is the early signal: 36 of 39 Brevard new licences this FY match a plan review (by licence digits, else address+ZIP); median 78 days earlier (p25 35, p75 135). Statewide: 1,488/1,673, median 56 days.
- Raw spike downloads are kept (git-ignored) in `logs/spike/`. The real headers are committed in `fixtures/headers/`.

### D2 · 2026-10-03 · Plan-review CSV replaces the licence-search scrape (user decision)
- Asked the user after D1; answer: "Use plan-review CSV (Recommended)". PRD, E2E_TESTS.md (fixtures, E2E-03..11, -13, -15, -18, -19, -28..-30, smoke, UT-04/05/09), CLAUDE.md, KICKOFF.md and .env.example updated before any spec was written. Source `dbpr_pending` became `dbpr_plan_review`; job `scrape-pending` became `import-plan-review`. No Playwright scraping; httpx only.
- Alternatives: keep the scrape as well (more breakage risk, marginal freshness), or the original plan (later signal, CAPTCHA risk).

### D3 · 2026-10-03 · Owner phone and email go into digests and CSVs (user decision)
- Answer: "Yes, include (Recommended)". Added L7, CSV columns `phone,email`, digest `Phone:`/`Email:` lines, and lead-detail contact testids.

### D4 · 2026-10-03 · Only in-county rows are stored
- The DBPR files are statewide (11k+ rows). `rows_fetched` counts every parsed row; only rows in `COUNTIES` become `raw_records`. Keeps the DB small; Orange-county fixture rows prove the filter.

### D5 · 2026-10-03 · Host ports for this machine
- LaunchLedger's containers already hold 127.0.0.1:8000 and :55432. OpeningSoon FL's Compose stack publishes the app on 127.0.0.1:8010 and Postgres on 127.0.0.1:55433 (`APP_HOST_PORT`, `POSTGRES_HOST_PORT` in `.env`). Test (8001) and walkthrough (8002) ports are unchanged. Final acceptance uses `BASE_URL=http://127.0.0.1:8010`.

### D6 · 2026-10-03 · Git identity
- No global `user.name`; set repo-local `Donald Miller <dkmills321@gmail.com>`, matching LaunchLedger.
