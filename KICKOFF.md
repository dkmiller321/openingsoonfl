# KICKOFF.md — paste the prompt below into Claude Code

Before you start, this folder should contain `CLAUDE.md`, `KICKOFF.md`, `KIT_FEEDBACK.md`, `.env.example` and `docs/`.

1. Run `cp .env.example .env`. Fixture and outbox mode need no keys.
2. Start Docker Desktop.
3. Start Claude Code in this folder and run `/mcp` to confirm the `playwright-headless` server is connected.

---

```
You are building OpeningSoon FL from a folder that holds only its build kit.

Read, in order: docs/PRD.md, docs/E2E_TESTS.md, CLAUDE.md. Follow CLAUDE.md's rules
for the whole build. Copy scaffolding patterns (not domain code) from
C:\Users\dkmil\vscode-workspace\LaunchLedger.

Phase 0: Preflight (fix what you can, ask only if blocked)
- Check that:
  - `docker ps` works.
  - This folder is a git repo. If not, run `git init` and make the kit files the first commit.
  - `git config user.name` is set.
  - `.env` exists. If not, copy .env.example.
  - `uv --version` works and `uv python install 3.12` succeeds.
  - Ports 8000, 8001, 8002 and 55432 are free.
- Save these checks as scripts/preflight.sh so they can be re-run.

Phase 1: Plan (then continue without waiting)
- Summarise the build in under 20 lines:
  - the stages
  - the fetcher/parser split and FixtureFetcher for the three DBPR CSVs
  - how lead_key matching and first_seen work
  - how you'll verify each stage with pytest-playwright and the
    `playwright-headless` MCP server
- List contradictions or gaps in the docs. If any block you, stop and ask.
  Otherwise record your assumptions in docs/DECISIONS.md and continue.

Phase 2: Tests first (stage 0)
- Scaffold stage 0: the uv project, FastAPI with /health, settings with fail-fast
  validation, the clock module, SQLAlchemy models + Alembic (with the include_name
  filter), docker-compose.yml (Postgres on 127.0.0.1:55432) and docker-compose.test.yml,
  the osfl_test and osfl_walk databases, every /test/* route, and the live_server fixture
  exactly as E2E_TESTS.md §1.2 describes.
- Finish the DBPR fixtures (E2E_TESTS.md §1.4). The spike already found the sources
  (DECISIONS.md D1) and saved the raw downloads in logs/spike/. Build the trimmed real
  samples and every canonical fixture from the real headers. Don't re-download.
- Write EVERY scenario in docs/E2E_TESTS.md as a spec in e2e/, marked by stage, plus
  the @smoke specs and the unit tests in §4. Use the data-testid contract exactly. Writing
  the specs in a parallel subagent from the contract worked well on the last build.
- Run `uv run pytest e2e --collect-only -q` to prove they all collect, then run the
  suite. E2E-00, -01 and -02 must pass. Everything else is expected to fail for now.
- Confirm the `playwright-headless` MCP server works: start the walkthrough server,
  navigate to /login and take a snapshot. Record the result in docs/VERIFICATION.md.
  Commit.

Phase 3: Build stages 1-5
- For each stage, follow the Workflow in CLAUDE.md:
  1. implement
  2. ruff + unit tests
  3. that stage's and all earlier stages' E2E specs green twice
  4. a `playwright-headless` walkthrough (E2E-19 every time from stage 4)
  5. VERIFICATION.md
  6. KIT_FEEDBACK.md
  7. commit
- Stage 1 is the operator's first sales tool. After it passes, also run the real
  sheet once: `uv run osfl import-weekly --county brevard` against live DBPR, then
  `uv run osfl export-csv --county brevard --since <7 days ago> --out
  exports/brevard-<date>.csv`. Report the row count. Don't commit the export.
- Stage 4 is the core promise. Don't start stage 5 until E2E-19 passes in both
  pytest and the MCP walkthrough.
- Never weaken an assertion to make it pass. Propose spec changes instead.

Phase 4: Final acceptance
- Run the Final acceptance steps in CLAUDE.md against the Docker Compose stack,
  including docs/DEPLOY.md and the KitForge report.
- Finish with a short report:
  - pass/fail totals
  - anything skipped and why
  - known issues
  - the exact commands I need to run the app and to produce this week's Brevard sheet
```

---

## Useful follow-up prompts

- **Resume after a break:** `Read CLAUDE.md, docs/VERIFICATION.md and docs/DECISIONS.md, find the last completed stage, and continue from the next one.`
- **Re-verify the core promise:** `Reset the walkthrough DB and walk E2E-19 and E2E-21 through the playwright-headless MCP server. Report each step and paste the subject lines from /test/outbox.`
- **This week's sheet:** `Run osfl import-weekly and osfl import-plan-review against live DBPR for Brevard, then export-csv for the last 7 days to exports/. Tell me the counts by stage and lead type.`
- **Live smoke:** `Start a dev server with SOURCE_MODE=live, run RUN_SMOKE=1 uv run pytest e2e -m smoke, and report the results.`
- **Source broke:** `A DBPR source is red. Download that one file once, diff its header against fixtures/headers/, fix the parser, refresh the fixtures, and re-run stages 1-2 + E2E-19.`
