# CLAUDE.md — OpeningSoon FL

Read these first, in order:

1. `docs/PRD.md`: what we're building and why. It's the source of truth for scope.
2. `docs/E2E_TESTS.md`: the acceptance contract. A feature exists when its scenarios pass.
3. This file: how to work.

If this file and the PRD disagree, the PRD wins. If the PRD and E2E_TESTS.md disagree, stop and ask.

The scaffolding pattern to copy is the user's repo at `C:\Users\dkmil\vscode-workspace\LaunchLedger`: uv project layout, settings, Alembic setup, Docker Compose, and the pytest-playwright `live_server` fixture. Copy patterns, not domain code.

## Stack (fixed)

| Layer | Choice |
|---|---|
| Runtime | Python 3.12, uv |
| Web | FastAPI + Uvicorn, Jinja2 templates, HTMX (vendored static file, no CDN) |
| Settings | pydantic-settings, read once in `osfl/settings.py` |
| Database | PostgreSQL 16, SQLAlchemy 2 **sync** engine (FastAPI runs sync routes in its threadpool), psycopg 3, Alembic |
| Jobs | APScheduler (in-process, `America/New_York`) |
| Fetching | httpx for all three DBPR CSV downloads. No scraping. Playwright is for tests only |
| Email | Resend HTTP API via httpx (`EMAIL_MODE=resend`), or the `outbox` table (`EMAIL_MODE=outbox`) |
| Auth | Starlette `SessionMiddleware` + `itsdangerous`, single password |
| CLI | Typer, entry point `osfl` |
| Tests | pytest, pytest-playwright, httpx |
| Deploy | Docker Compose: `app` + `postgres` (+ `docker-compose.test.yml` override) |

These packages are pre-approved, along with their normal transitive dependencies. **Ask before adding any other runtime dependency.** Dev-only tooling (ruff, mypy, type stubs) is fine.

Don't use async SQLAlchemy: psycopg async doesn't run on Windows' default event loop.

## Hard rules

- **Tests first.** In stage 0, write every scenario in `docs/E2E_TESTS.md` as a spec, plus every unit test in §4. Specs may fail until their stage; they may never be weakened to pass. If a scenario is wrong, say so and propose the change. Never silently edit an assertion, a testid, a fixture row or an exact string from §1.5.
- **Nothing is done until it has run.** For every claim that something works, state the command you ran and what you observed.
- **No network in tests.** `SOURCE_MODE=fixture` and `EMAIL_MODE=outbox` for everything except `@smoke`. Fixtures replace only the fetcher. Parser, classifier, matcher and run bookkeeping always run for real.
- **Be polite to government sites.** One request at a time, at least 2 s apart, with `FETCH_USER_AGENT`. Never re-download DBPR files to debug a parser. Debug against the saved fixture instead.
- **Selectors are a contract.** Use the `data-testid` values in E2E_TESTS.md §1.6 exactly.
- **One clock.** Every "now" goes through `osfl.clock.now()`, which honours `FAKE_NOW` / `POST /test/clock`. Never call `datetime.now()` elsewhere.
- **Respect the non-goals.** No vendor logins, no billing, no Sunbiz, permits or liquor adapters, no enrichment APIs, no extra counties ingested.
- **Licences:** copy functionality only from ConstructConnect, BuildZoom and Apollo. No code, names or branding.
- **No TODOs or stubs** in committed code. Implement it, or record it as out of scope in `docs/DECISIONS.md`.
- **Secrets stay in `.env`.** Never log `RESEND_API_KEY`, `ADMIN_PASSWORD` or `SESSION_SECRET`.
- **ASCII-only CLI output.** The Windows console is cp1252.

## Conventions

- Layout:
  - `osfl/main.py`: app factory.
  - `osfl/settings.py`, `osfl/clock.py`, `osfl/db.py`, `osfl/models.py`.
  - `osfl/sources/`: one module per source, each with `fetch_*` and `parse_*`, plus `fixtures.py` for `FixtureFetcher`.
  - `osfl/leads/`: `normalise.py`, `classify.py`, `matcher.py`, all pure.
  - `osfl/digests/`: builder, CSV, sender with outbox and Resend.
  - `osfl/health.py`, `osfl/jobs.py` (the one function per job that CLI, scheduler and `/test/run` all call), `osfl/web/` (routes + templates), `osfl/testing/` (test routes), `osfl/cli.py`.
  - Other folders: `alembic/`, `fixtures/`, `tests/`, `e2e/`, `scripts/`, `logs/` (git-ignored), `docs/`.
- Env is read once in `osfl/settings.py`. Nothing else reads `os.environ`. A missing required key fails startup with a message naming the key.
- Use `127.0.0.1`, never `localhost`, in URLs, defaults and docs.
- Give Alembic's `env.py` an `include_name` filter that only includes our own tables (and skips `alembic_version`) **before** the first autogenerate.
- Each source run is one transaction: raw records, leads and events commit together, or not at all. Then a separate short transaction writes the `source_runs` row, so failures are recorded too.
- De-duplication lives in database unique constraints (`raw_records(source, content_hash)`, `leads(lead_key)`, `deliveries(vendor_id, lead_id)`, one scheduled digest per vendor and period). Code relies on them, not on reads-then-writes.
- Errors propagate to one handler per route or job. No blanket try/except, retry decorators or logging wrappers, except the fetcher's retry (I5).
- UI style: white background, neutral greys, black primary buttons, pill-shaped inputs, no component library. Keep it plain.
- Commit after each stage with the message `stage N: <summary>`.

## Workflow

Work through the stages in `docs/PRD.md` → Milestones, in order, **without waiting for confirmation between stages** unless you're blocked.

For each stage:

1. Implement the stage.
2. Run `uv run ruff check . && uv run pytest tests`.
3. Run `uv run pytest e2e -m "not smoke and (stage0 or … or stageN)"`. Every scenario for this stage **and every earlier stage** must pass, twice in a row.
4. **Walk the stage with the `playwright-headless` MCP server** (E2E_TESTS.md §5), on the separate walkthrough server and database, never at the same time as pytest. From stage 4 on, walk E2E-19 every time.
5. Append to `docs/VERIFICATION.md`: the stage, the commands with pass/fail counts, each walked scenario as `E2E-xx: pass | fail — note`, and anything surprising.
6. Append to `KIT_FEEDBACK.md` anything the kit got wrong or left out, in that file's format. Do this as it happens, not at the end.
7. Commit.

Stop and ask when:

- a change would alter the PRD's scope, a test assertion, a testid, a fixture row or an exact string in E2E_TESTS.md §1.5,
- a dependency outside the approved list seems necessary,
- the same failure survives three genuine fix attempts.

Otherwise decide, record the decision in `docs/DECISIONS.md` (date, decision, why, alternatives), and keep going.

## Final acceptance

1. `docker compose -f docker-compose.yml -f docker-compose.test.yml up -d --build`. The test override sets `TEST_ROUTES=1`, `SOURCE_MODE=fixture`, `EMAIL_MODE=outbox`, `SCHEDULER_ENABLED=0`, `ADMIN_PASSWORD=test-admin-pw`, `MAX_VENDORS_PER_CATEGORY=2` and `APP_BASE_URL=http://127.0.0.1:8000`, plus the operator values from E2E_TESTS.md §1.2. Wait for `GET http://127.0.0.1:8000/health` to return 200.
2. Run `BASE_URL=http://127.0.0.1:8000 uv run pytest e2e -m "not smoke"`. Everything must pass. Run it three times and record any flaky spec (the target is 0).
3. Walk every P0 scenario through `playwright-headless` against the container, with E2E-19 last.
4. Bring the stack up without the test override (`docker compose up -d --build`, `SCHEDULER_ENABLED=1`). Check that `/test/reset` returns 404 and the scheduler logs its 5 jobs with their next run times.
5. Start a dev server with `SOURCE_MODE=live` and run `RUN_SMOKE=1 uv run pytest e2e -m smoke`. Report the results, including how many Brevard leads each live file produced. SMOKE-4 runs only if `RESEND_API_KEY` is set.
6. Write `docs/DEPLOY.md`. It covers:
   - VPS prerequisites
   - `.env` for production
   - a Caddy reverse proxy with HTTPS
   - backups (`pg_dump` cron)
   - Resend domain verification (SPF/DKIM)
   - how to check the scheduler is running
7. Write the final summary in `docs/VERIFICATION.md`: totals, skipped tests and why, known issues, and the exact commands to run OpeningSoon FL locally and to produce this week's Brevard sheet (`osfl import-weekly` + `osfl export-csv`).
8. **Report to KitForge.** Send `KIT_FEEDBACK.md` as one report, using the command in that file. If KitForge isn't running, say so in one line and stop. Don't retry.
