# OpeningSoon FL

**Finds new restaurants in Brevard County, Florida, weeks before they open, and sells those leads to the vendors who want to reach them first.**

Florida's DBPR publishes free daily files. A restaurant's *plan review* is filed before construction starts and includes the owner's phone and email. Its *licence* comes around opening day. OpeningSoon FL joins the two, so a POS reseller, insurer or pest-control company hears about a restaurant a median of about two months before it's licensed.

Real numbers from the first import (Oct 3, 2026):

| Measure | Value |
| --- | --- |
| Brevard leads | 251 |
| Leads with an owner phone | 243 |
| Median head start before the licence | 58 days |
| Leads placed on the map | 76% |

## Features

| Area | What it does |
| --- | --- |
| **Data sources** | Daily, polite downloads of `HR_plan_review.csv` (earliest, with contacts), `newfood.csv` (new licences) and `chgownr_food.csv` (ownership changes). Manual CSV upload as a fallback |
| **Import engine** | Classifies each row (new restaurant, ownership change, food truck; caterers and vending skipped). Merges rows about the same restaurant by licence number, else name + address + ZIP. Idempotent re-runs. Geocodes with the US Census geocoder |
| **Leads** | One record per restaurant: stage timeline (plan review → licensed), "days ahead", licensee, phone and email, a cuisine icon guessed from the name, operator notes, rename and hide |
| **Vendor digests** | Vendors subscribe by category, county and cadence (weekly Monday 7:00 ET or daily 7:00 ET). The email lists only leads they haven't seen and attaches a CSV. Each lead reaches a vendor only once. Preview, test send, one-click unsubscribe, CAN-SPAM footer, category cap warning |
| **Map** | Cuisine pins coloured by stage, clustering, a 90-day time slider with Play, a radius filter from a town or a map click, and Mapbox Light, Dark, Streets, Outdoors and Satellite styles (greyscale OpenStreetMap without a token) |
| **Pipeline board** | "In plan review" and "Licensed" columns of lead cards |
| **Source health** | Run history per source (green, amber, red). Email alerts when a run fails, returns zero rows, sees changed columns, or goes stale |
| **Appearance** | Light, Dark or System theme, and six colour palettes including a colour-blind safe one |
| **Scheduler** | In-app, Eastern time: plan reviews 05:00, licences 06:00, digests 07:00, health checks hourly at :15 |

The operator console has pages for Dashboard, Leads, Map, Pipeline, Vendors and Sources. Vendors never log in; they only receive email.

## Quick start

```bash
cp .env.example .env                 # fixture data + outbox email, no keys needed
docker compose up -d --build         # app on http://127.0.0.1:8010, password = ADMIN_PASSWORD
```

To load real Brevard data, set `SOURCE_MODE=live` and a real contact address in `FETCH_USER_AGENT`, then run:

```bash
uv sync
uv run osfl import-plan-review --county brevard
uv run osfl import-weekly --county brevard
uv run osfl export-csv --county brevard --since 2026-09-26 --out exports/brevard-week.csv
```

### CLI

| Command | What it does |
| --- | --- |
| `osfl import-plan-review` / `osfl import-weekly` | Import DBPR plan reviews / licences (`--file`, `--dir` for local copies) |
| `osfl export-csv` | Write the lead sheet for a county since a date |
| `osfl send-digests --cadence weekly` | Send the digests due now |
| `osfl check-health` | Source statuses and stale alerts |
| `osfl geocode [--retry-unmatched]` | Place leads on the map (runs after imports anyway) |
| `osfl rebuild-leads` | Re-derive leads from stored raw rows after a parser fix |

### Configuration

All settings live in `.env` (see `.env.example`, every variable is commented). The ones you'll touch:

| Variable | Purpose |
| --- | --- |
| `ADMIN_PASSWORD`, `SESSION_SECRET` | Operator login |
| `SOURCE_MODE` | `fixture` (tests, default) or `live` (real DBPR) |
| `EMAIL_MODE`, `RESEND_API_KEY`, `EMAIL_FROM` | `outbox` (stored, not sent) or `resend` |
| `OPERATOR_EMAIL`, `OPERATOR_POSTAL_ADDRESS` | Alerts, test sends, CAN-SPAM footer |
| `MAPBOX_TOKEN` | Optional public `pk.` token for Mapbox basemaps |
| `ELEVENLABS_API_KEY` | Only for the demo video |

## Develop and test

Every feature was written as a browser test before it was built (`docs/E2E_TESTS.md`).

```bash
uv sync && uv run playwright install chromium
docker compose up -d postgres
uv run pytest tests                          # 48 unit tests
uv run pytest e2e -m "not smoke"             # 40 E2E specs (starts its own server on :8001)
RUN_SMOKE=1 SOURCE_MODE=live uv run pytest e2e -m smoke   # live DBPR, manual only
uv run python scripts/walk_server.py start   # walkthrough server on :8002 for the Playwright MCP
```

**Stack:** Python 3.12, FastAPI, Jinja2 + HTMX, SQLAlchemy + Alembic, PostgreSQL 16, APScheduler, httpx, Leaflet + markercluster, Docker Compose, pytest-playwright.

## Demo video

```bash
uv run python scripts/demo/run.py   # needs ELEVENLABS_API_KEY in .env and ffmpeg
```

This produces a narrated 2.5-minute feature tour, `scripts/demo/out/openingsoon-demo.mp4`:

1. Copies the local real-data database into `osfl_demo` and starts a demo server on :8004 with example vendors.
2. Generates one ElevenLabs clip per narration line. Clips are cached, so re-runs only pay for lines you change.
3. Records the tour in Playwright at 1280x720.
4. Lines up the audio with ffmpeg.

The script and the steps live in `scripts/demo/flow.py`.

## Deploy

See [docs/DEPLOY.md](docs/DEPLOY.md): one small VPS, Docker Compose, Caddy for HTTPS, nightly `pg_dump`, and Resend domain verification.

## Docs

[PRD](docs/PRD.md) · [Acceptance tests](docs/E2E_TESTS.md) · [Decisions](docs/DECISIONS.md) · [Verification log](docs/VERIFICATION.md) · [Deploy](docs/DEPLOY.md)

*Data: Florida DBPR public records (Ch. 119, F.S.). Map data © OpenStreetMap contributors and © Mapbox.*
