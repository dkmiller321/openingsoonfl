"""The one function per job. The CLI, the scheduler and POST /test/run all call these."""

from __future__ import annotations

import logging
import traceback
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select

from osfl import clock
from osfl.db import session_scope
from osfl.ingest import ingest
from osfl.models import SourceRun
from osfl.settings import get_settings
from osfl.sources.dbpr import PLAN_REVIEW, SOURCE_FILES, WEEKLY, HeaderMismatch, parse
from osfl.sources.fetch import Fetcher, FetchError, FixtureFetcher, LiveFetcher

log = logging.getLogger("osfl.jobs")


def default_fetcher(fixture: str | None) -> Fetcher:
    settings = get_settings()
    if fixture:
        return FixtureFetcher(fixture, settings.fixtures_dir)
    if settings.source_mode == "fixture":
        raise FetchError(
            "SOURCE_MODE=fixture: pass a fixture (or --dir/--file) or set SOURCE_MODE=live"
        )
    return LiveFetcher(settings.fetch_user_agent, settings.fetch_min_interval_s)


def _url(filename: str) -> str:
    settings = get_settings()
    return {
        "newfood.csv": settings.dbpr_newfood_url,
        "chgownr_food.csv": settings.dbpr_chgownr_url,
        "HR_plan_review.csv": settings.dbpr_plan_review_url,
    }[filename]


def _zero_rows_problem(source: str, before_run_id: int) -> bool:
    """Zero rows is a problem only when the previous 4 weeks of good runs averaged above 0."""
    since = clock.now() - timedelta(days=28)
    with session_scope() as session:
        avg = session.scalar(
            select(func.avg(SourceRun.rows_fetched)).where(
                SourceRun.source == source,
                SourceRun.status == "ok",
                SourceRun.id < before_run_id,
                SourceRun.started_at >= since,
            )
        )
    return bool(avg and avg > 0)


def run_source(
    source: str,
    fetcher: Fetcher,
    trigger: str,
    files: tuple[str, ...] | None = None,
    counties: list[str] | None = None,
) -> dict[str, Any]:
    """Fetch, parse and ingest one source as one transaction; always record a source_runs row."""
    counties = counties or get_settings().county_list
    started = clock.now()
    with session_scope() as session:
        run = SourceRun(source=source, trigger=trigger, started_at=started, status="running")
        session.add(run)
        session.flush()
        run_id = run.id

    outcome: dict[str, Any] = {
        "run_id": run_id, "status": "ok", "rows_fetched": 0, "rows_new": 0,
        "leads_created": 0, "leads_updated": 0, "error": None,
    }
    problem = None
    try:
        records = []
        for filename in files or SOURCE_FILES[source]:
            records.extend(parse(source, filename, fetcher.fetch(filename, _url(filename))))
        outcome["rows_fetched"] = len(records)
        in_county = [r for r in records if r.county in counties]
        with session_scope() as session:
            result = ingest(session, in_county, run_id, started, clock.today_et())
        outcome.update(
            rows_new=result.rows_new,
            leads_created=result.leads_created,
            leads_updated=result.leads_updated,
        )
        if outcome["rows_fetched"] == 0 and _zero_rows_problem(source, run_id):
            problem = "zero rows"
    except HeaderMismatch as exc:
        outcome.update(status="failed", error=str(exc))
        problem = "columns changed"
    except FetchError as exc:
        outcome.update(status="failed", error=str(exc))
        problem = "run failed"
    except Exception as exc:  # the job's one handler: record any failure, keep the trace
        log.error("%s run %s failed\n%s", source, run_id, traceback.format_exc())
        outcome.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        problem = "run failed"

    with session_scope() as session:
        run = session.get(SourceRun, run_id)
        assert run is not None
        run.finished_at = clock.now()
        run.status = outcome["status"]
        run.rows_fetched = outcome["rows_fetched"]
        run.rows_new = outcome["rows_new"]
        run.leads_created = outcome["leads_created"]
        run.leads_updated = outcome["leads_updated"]
        run.problem = problem
        run.error = outcome["error"]
    if problem:
        from osfl.health import alert_for_run

        alert_for_run(source, problem, outcome["error"])
    return outcome


def import_weekly(fixture: str | None = None, trigger: str = "scheduled", **kw: Any) -> dict:
    return run_source(WEEKLY, kw.pop("fetcher", None) or default_fetcher(fixture), trigger, **kw)


def import_plan_review(fixture: str | None = None, trigger: str = "scheduled", **kw: Any) -> dict:
    return run_source(
        PLAN_REVIEW, kw.pop("fetcher", None) or default_fetcher(fixture), trigger, **kw
    )


def send_digests_weekly(fixture: str | None = None, trigger: str = "scheduled") -> dict:
    from osfl.digests.builder import send_scheduled_digests

    return send_scheduled_digests("weekly")


def send_digests_daily(fixture: str | None = None, trigger: str = "scheduled") -> dict:
    from osfl.digests.builder import send_scheduled_digests

    return send_scheduled_digests("daily")


def check_health(fixture: str | None = None, trigger: str = "scheduled") -> dict:
    from osfl.health import check_health as run_check

    return run_check()


JOBS: dict[str, Callable[..., dict[str, Any]]] = {
    "import-weekly": import_weekly,
    "import-plan-review": import_plan_review,
    "send-digests-weekly": send_digests_weekly,
    "send-digests-daily": send_digests_daily,
    "check-health": check_health,
}


def run_job(name: str, fixture: str | None = None, trigger: str = "scheduled") -> dict[str, Any]:
    return JOBS[name](fixture=fixture, trigger=trigger)
