"""`osfl` command line. Output is ASCII only (the Windows console is cp1252)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import typer

from osfl.sources.fetch import FetchError, LocalFetcher

app = typer.Typer(add_completion=False, no_args_is_help=True)


def _report(result: dict) -> None:
    typer.echo(
        f"{result['status']}: fetched {result['rows_fetched']} rows, {result['rows_new']} new, "
        f"{result['leads_created']} leads created, {result['leads_updated']} updated"
    )
    if result["error"]:
        typer.echo(f"error: {result['error']}")
    if result["status"] != "ok":
        raise typer.Exit(1)


@app.command("import-weekly")
def import_weekly(
    county: str = typer.Option("brevard", help="County to keep"),
    dir: Path | None = typer.Option(None, help="Folder holding newfood.csv and chgownr_food.csv"),  # noqa: A002
) -> None:
    """Import DBPR new licences and owner changes."""
    from osfl import jobs

    fetcher = LocalFetcher(folder=dir) if dir else jobs.default_fetcher(None)
    _report(jobs.import_weekly(trigger="cli", fetcher=fetcher, counties=[county.lower()]))


@app.command("import-plan-review")
def import_plan_review(
    county: str = typer.Option("brevard", help="County to keep"),
    file: Path | None = typer.Option(None, help="A local HR_plan_review.csv"),
) -> None:
    """Import DBPR plan reviews."""
    from osfl import jobs

    fetcher = (
        LocalFetcher(files={"HR_plan_review.csv": file.read_bytes()})
        if file
        else jobs.default_fetcher(None)
    )
    _report(jobs.import_plan_review(trigger="cli", fetcher=fetcher, counties=[county.lower()]))


@app.command("export-csv")
def export_csv(
    county: str = typer.Option("brevard"),
    since: str = typer.Option(..., help="First-seen date, YYYY-MM-DD"),
    out: Path = typer.Option(..., help="Where to write the CSV"),
) -> None:
    """Write the lead sheet for one county."""
    from osfl.db import session_scope
    from osfl.leads.export import leads_csv
    from osfl.leads.queries import LeadFilter, lead_query

    with session_scope() as session:
        rows = list(session.scalars(
            lead_query(LeadFilter(county=county, since=date.fromisoformat(since)))
        ))
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(leads_csv(rows), encoding="utf-8", newline="")
    typer.echo(f"Exported {len(rows)} leads to {out}")


@app.command("send-digests")
def send_digests(cadence: str = typer.Option("weekly", help="weekly or daily")) -> None:
    """Send the digests due now."""
    from osfl.digests.builder import send_scheduled_digests

    result = send_scheduled_digests(cadence)
    typer.echo(f"sent {result['emails_sent']} digests")


@app.command("rebuild-leads")
def rebuild_leads() -> None:
    """Re-derive every lead from its stored raw records (after a parser fix)."""
    from osfl.db import session_scope
    from osfl.ingest import rebuild_leads as run_rebuild

    with session_scope() as session:
        count = run_rebuild(session)
    typer.echo(f"rebuilt {count} leads")


@app.command("geocode")
def geocode(
    retry_unmatched: bool = typer.Option(False, help="Also retry leads that failed before"),
) -> None:
    """Geocode leads that have no map position yet (US Census batch geocoder)."""
    from osfl.geo import geocode_pending

    result = geocode_pending(retry_unmatched=retry_unmatched)
    typer.echo(f"geocoded: {result['matched']} matched, {result['unmatched']} unmatched")


@app.command("check-health")
def check_health() -> None:
    """Report source statuses and send stale alerts."""
    from osfl.health import check_health as run_check

    result = run_check()
    for source, status in result["statuses"].items():
        typer.echo(f"{source}: {status}")
    typer.echo(f"alerts sent: {result['alerts_sent']}")


def main() -> None:
    try:
        app()
    except FetchError as exc:
        typer.echo(f"error: {exc}")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
