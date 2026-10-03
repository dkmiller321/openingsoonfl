"""Digest periods: the ISO week (weekly) or the ET calendar day (daily)."""

from datetime import date, datetime, timedelta

from osfl.clock import ET


def digest_period(now: datetime, cadence: str) -> str:
    local = now.astimezone(ET)
    if cadence == "daily":
        return local.date().isoformat()
    year, week, _ = local.isocalendar()
    return f"{year}-W{week:02d}"


def week_start(now: datetime) -> date:
    """Monday of the ET week containing `now`."""
    local = now.astimezone(ET).date()
    return local - timedelta(days=local.weekday())
