"""In-process schedule (America/New_York). Every job is the same function the CLI calls."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from osfl.clock import ET

log = logging.getLogger("osfl.scheduler")

SCHEDULE: dict[str, dict[str, str]] = {
    "import-weekly": {"hour": "6", "minute": "0"},
    "import-plan-review": {"hour": "5", "minute": "0"},
    "send-digests-daily": {"hour": "7", "minute": "0"},
    "send-digests-weekly": {"day_of_week": "mon", "hour": "7", "minute": "0"},
    "check-health": {"minute": "15"},
}


def _trigger(job: str) -> CronTrigger:
    return CronTrigger(timezone=ET, **SCHEDULE[job])


def next_runs(now: datetime) -> list[tuple[str, str]]:
    """Next fire time of each job after `now`, as UTC ISO strings ending in Z."""
    out = []
    for job in SCHEDULE:
        when = _trigger(job).get_next_fire_time(None, now.astimezone(ET))
        assert when is not None
        out.append((job, when.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")))
    return out


def _run(job: str) -> None:
    from osfl.jobs import run_job

    result = run_job(job, trigger="scheduled")
    log.info("scheduled %s -> %s", job, result)


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=ET)
    for job in SCHEDULE:
        scheduler.add_job(_run, _trigger(job), args=[job], id=job, max_instances=1,
                          coalesce=True, misfire_grace_time=3600)
    scheduler.start()
    for job in scheduler.get_jobs():
        log.warning("scheduler: %s next run %s", job.id, job.next_run_time.isoformat())
    return scheduler
