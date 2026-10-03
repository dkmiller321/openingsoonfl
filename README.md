# OpeningSoon FL

Early alerts about new Brevard County restaurants, for the vendors who want to sell to them first.

- **Sources** (Florida DBPR public records, free CSV downloads):
  - `HR_plan_review.csv`: plan reviews, with owner phone and email, a median of about 2 months before the licence.
  - `newfood.csv` / `chgownr_food.csv`: new licences and ownership changes.
- **Leads:** one per restaurant, merged by licence number or by name, address and ZIP. Each lead has a stage timeline and a "days ahead" figure.
- **Digests:** each vendor gets the leads it hasn't seen yet, weekly or daily, with a CSV attached.
- **Admin console:** leads, vendors, digest preview and test send, source health, manual upload.
- **Map and pipeline:** leads geocoded with the US Census geocoder and shown as cuisine-icon pins on a greyscale OpenStreetMap, with a 90-day time slider and a radius filter. A two-column pipeline board shows plan review vs licensed.

## Run it locally

```bash
cp .env.example .env                 # fixture + outbox mode, no keys needed
docker compose up -d --build         # app on http://127.0.0.1:8010 (password: ADMIN_PASSWORD in .env)
```

Real data: set `SOURCE_MODE=live` (and a real contact in `FETCH_USER_AGENT`), then:

```bash
uv sync
uv run osfl import-plan-review --county brevard
uv run osfl import-weekly --county brevard
uv run osfl export-csv --county brevard --since 2026-09-26 --out exports/brevard-week.csv
uv run osfl geocode                  # runs after imports anyway; --retry-unmatched to retry misses
uv run osfl rebuild-leads            # after a parser fix, re-derive leads from stored raw rows
```

## Develop and test

```bash
uv sync && uv run playwright install chromium
docker compose up -d postgres
uv run pytest tests                          # unit tests
uv run pytest e2e -m "not smoke"             # E2E (starts its own server on 127.0.0.1:8001)
RUN_SMOKE=1 SOURCE_MODE=live uv run pytest e2e -m smoke   # live DBPR, manual only
uv run python scripts/walk_server.py start   # walkthrough server on :8002 for the Playwright MCP
```

Docs: [PRD](docs/PRD.md) · [acceptance contract](docs/E2E_TESTS.md) · [decisions](docs/DECISIONS.md) · [verification log](docs/VERIFICATION.md) · [deploy](docs/DEPLOY.md).
