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

### D7 · 2026-10-03 · E2E-30 expected check-health time corrected (user decision)
- §1.5 schedules `check-health` hourly at :15 ET, but E2E-30 expected `2026-10-05T09:45:00Z` (05:45 ET) after 05:30 ET. Asked the user; answer: "Fix the assertion to 10:15Z (Recommended)". Spec and E2E_TESTS.md now expect `2026-10-05T10:15:00Z`.

### D8 · 2026-10-03 · Lead identities live in `lead_keys`
- PRD lists `leads.lead_key` (kept, unique). A lead can be known by several identities (`LIC:<digits>` from any licence or plan review, `K:<name|address|zip>` per spelling), so `lead_keys(key -> lead_id)` stores them all. Licence digits win over name/address when both match different leads. Needed for E2E-09b (misspelt address, same licence number).

### D9 · 2026-10-03 · Small behaviours the contract left open
- Login always lands on `/` (E2E-12), so there is no `next=` redirect.
- A custom display name (L5) overrides the record name everywhere, including digests and CSVs.
- Digest emails go out inside the transaction that records deliveries; if sending raises, the deliveries roll back. In outbox mode the email row commits in its own transaction.
- Unsubscribe is a GET (as E2E-23 requires). Mail scanners that prefetch links could unsubscribe a vendor. Revisit with a confirm button or `List-Unsubscribe-Post` before scaling.
- A scheduled source job in `SOURCE_MODE=fixture` (no fixture given) fails with a logged FetchError and records no run. Production must set `SOURCE_MODE=live` (docs/DEPLOY.md).

### D10 · 2026-10-03 · Map stack (stage 6, user-approved scope: admin map + icons + slider + radius + board)
- Leaflet 1.9.4 + Leaflet.markercluster 1.5.3, vendored under `osfl/web/static/vendor/leaflet/` (BSD-2 / MIT). Treated as approved: the user chose the map features in this conversation.
- Tiles: OpenStreetMap standard tiles with a greyscale CSS filter, to match the grey UI. CARTO Positron now returns "API KEY REQUIRED". OSM's tile policy allows light, attributed use like a single-operator admin page. For heavy or public use, switch `MAP_TILE_URL` to a keyed provider (Stadia, MapTiler).
- Geocoder: US Census batch geocoder (free, no key, public domain), run after each import that touched leads. It's best effort: a failure logs and leaves leads pending. A unit-stripping retry for misses. Nominatim was rejected as a fallback because it resolved misses only to road midpoints (misleading pins).
- Icons: emoji per cuisine from keyword/brand rules (`osfl/leads/cuisine.py`). No icon library, no logos: new restaurants have no logos yet, and Google Places costs money and restricts use.
- Map data: `/map/data.json` returns every non-hidden lead; stage/type/since/slider/radius filtering is client-side so the slider is instant.

### D11 · 2026-10-03 · Swapped phone column in chgownr_food.csv
- Some rows carry the county code in "Primary Phone Number" and the phone in "Mailing County Code"/"Secondary Phone Number". `best_phone()` picks the first value with 10+ digits. Added `osfl rebuild-leads` to re-derive leads from stored raw rows after parser fixes (content hashes don't change, so a re-import alone would skip them).

### D12 · 2026-10-03 · Appearance and Mapbox basemaps (user request)
- Themes: Light (default), Dark, System. Palettes: Classic, Ocean, Sunset, Forest, Grape, Colour-blind safe (Okabe-Ito orange/blue). All colours are CSS variables on `<html data-theme data-palette>`; tints use `color-mix()`. Choice saved in the `osfl_appearance` cookie (1 year), read server-side so there's no flash. Single operator, so no per-user table.
- Basemaps: when `MAPBOX_TOKEN` is set, Mapbox raster styles (light-v11, dark-v11, streets-v12, outdoors-v12, satellite-streets-v12) with a picker; "Auto" follows the theme. Without a token, greyscale OSM (inverted in dark). The token is a public `pk.` token embedded in the page, which is normal for Mapbox. Restrict it by URL in the Mapbox account before deploying. Mapbox geocoding isn't used (its free results can't be stored).
