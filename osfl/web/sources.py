"""Source health page and manual CSV upload (H3, I7)."""

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse

from osfl.db import DbSession
from osfl.health import SOURCE_LABELS, SOURCES, recent_runs, statuses
from osfl.jobs import run_source
from osfl.sources.dbpr import PLAN_REVIEW, WEEKLY
from osfl.sources.fetch import LocalFetcher
from osfl.web.common import flash, render, require_login

router = APIRouter(dependencies=[Depends(require_login)])

UPLOAD_KINDS = {
    "newfood.csv": (WEEKLY, "New restaurant licences (newfood.csv)"),
    "chgownr_food.csv": (WEEKLY, "Owner changes (chgownr_food.csv)"),
    "HR_plan_review.csv": (PLAN_REVIEW, "Plan reviews (HR_plan_review.csv)"),
}


@router.get("/sources")
def sources_page(request: Request, session: DbSession):
    current = statuses(session)
    sources = [
        {"key": s, "label": SOURCE_LABELS[s], "status": current[s], "runs": recent_runs(session, s)}
        for s in SOURCES
    ]
    return render(request, "sources.html", active="sources", sources=sources,
                  kinds=UPLOAD_KINDS)


@router.post("/sources/upload")
async def sources_upload(
    request: Request, file: UploadFile = File(...), kind: str = Form("newfood.csv")
):
    if kind not in UPLOAD_KINDS:
        kind = "newfood.csv"
    source, _ = UPLOAD_KINDS[kind]
    data = await file.read()
    result = run_source(source, LocalFetcher(files={kind: data}), "manual", files=(kind,))
    if result["status"] == "ok":
        flash(request, "upload",
              f"{result['rows_fetched']} rows, {result['leads_created']} new leads")
    else:
        flash(request, "upload-error", f"Upload failed: {result['error']}")
    return RedirectResponse("/sources", status_code=303)
