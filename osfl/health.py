"""Source health (H1-H3): status per source, alerts on bad runs and on staleness."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from osfl import clock
from osfl.db import session_scope
from osfl.models import HealthAlert, SourceRun
from osfl.settings import get_settings
from osfl.sources.dbpr import PLAN_REVIEW, WEEKLY

SOURCES = (WEEKLY, PLAN_REVIEW)
STALE_AFTER = {WEEKLY: timedelta(days=8), PLAN_REVIEW: timedelta(hours=36)}
SOURCE_LABELS = {WEEKLY: "DBPR licences (newfood + chgownr)", PLAN_REVIEW: "DBPR plan reviews"}


@dataclass
class RunInfo:
    finished_at: datetime
    status: str
    problem: str | None


def health_status(source: str, runs: list[RunInfo], now: datetime) -> str:
    """`runs` newest first. Red = last run had a problem; amber = stale or never run."""
    if not runs:
        return "amber"
    if runs[0].problem:
        return "red"
    good = next((r for r in runs if r.status == "ok"), None)
    if good is None or now - good.finished_at > STALE_AFTER[source]:
        return "amber"
    return "green"


def recent_runs(session: Session, source: str, limit: int = 10) -> list[SourceRun]:
    return list(
        session.scalars(
            select(SourceRun)
            .where(SourceRun.source == source, SourceRun.status != "running")
            .order_by(SourceRun.id.desc())
            .limit(limit)
        )
    )


def _info(run: SourceRun) -> RunInfo:
    return RunInfo(finished_at=run.finished_at or run.started_at, status=run.status,
                   problem=run.problem)


def statuses(session: Session) -> dict[str, str]:
    now = clock.now()
    return {s: health_status(s, [_info(r) for r in recent_runs(session, s)], now) for s in SOURCES}


def _alert(source: str, reason: str, detail: str) -> None:
    from osfl.digests.sender import send_email

    settings = get_settings()
    subject = f"[OpeningSoon FL] Source problem: {source} - {reason}"
    text = (
        f"{SOURCE_LABELS[source]} ({source}): {reason}.\n\n{detail}\n\n"
        f"Check {settings.app_base_url}/sources"
    )
    html = (
        f"<p><strong>{SOURCE_LABELS[source]}</strong> ({source}): {reason}.</p>"
        f"<pre>{_escape(detail)}</pre>"
        f'<p><a href="{settings.app_base_url}/sources">Open the sources page</a></p>'
    )
    send_email([settings.operator_email], subject, html, text, [])


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def alert_for_run(source: str, problem: str, error: str | None) -> None:
    details = {
        "zero rows": "The run fetched 0 rows, but the last 4 weeks averaged more.",
    }
    _alert(source, problem, error or details.get(problem, ""))


def check_health() -> dict:
    """Hourly: report statuses and send one 'stale' alert per source per stale episode."""
    now = clock.now()
    alerts = 0
    with session_scope() as session:
        current = statuses(session)
        to_alert = []
        for source, status in current.items():
            if status != "amber":
                continue
            last_good = session.scalar(
                select(SourceRun.id)
                .where(SourceRun.source == source, SourceRun.status == "ok")
                .order_by(SourceRun.id.desc())
                .limit(1)
            )
            inserted = session.execute(
                insert(HealthAlert)
                .values(source=source, reason="stale", episode=str(last_good or "none"),
                        sent_at=now)
                .on_conflict_do_nothing(constraint="uq_health_episode")
                .returning(HealthAlert.id)
            ).scalar_one_or_none()
            if inserted is not None:
                to_alert.append(source)
    for source in to_alert:
        limit = STALE_AFTER[source]
        hours = int(limit.total_seconds() // 3600)
        _alert(source, "stale", f"No successful run in the last {hours} hours.")
        alerts += 1
    return {"statuses": current, "alerts_sent": alerts}
