"""Digest preview + test send (E5) and the public unsubscribe page (E7)."""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from osfl.db import DbSession
from osfl.digests.builder import preview, send_test
from osfl.models import Vendor
from osfl.web.common import flash, render, require_login

router = APIRouter()
admin = APIRouter(dependencies=[Depends(require_login)])


@admin.get("/vendors/{vendor_id}/digest/preview")
def digest_preview(vendor_id: int, request: Request, session: DbSession):
    vendor = session.get(Vendor, vendor_id)
    if vendor is None:
        raise HTTPException(404, "Vendor not found")
    email = preview(session, vendor)
    return render(request, "digest_preview.html", active="vendors", vendor=vendor, email=email)


@admin.post("/vendors/{vendor_id}/digest/test")
def digest_test(vendor_id: int, request: Request, session: DbSession):
    vendor = session.get(Vendor, vendor_id)
    if vendor is None:
        raise HTTPException(404, "Vendor not found")
    to = send_test(session, vendor)
    flash(request, "test-sent", f"Test sent to {to}")
    return RedirectResponse(f"/vendors/{vendor_id}/digest/preview", status_code=303)


@router.get("/unsubscribe/{token}")
def unsubscribe(token: str, request: Request, session: DbSession):
    vendor = session.scalar(select(Vendor).where(Vendor.unsubscribe_token == token))
    if vendor is None:
        return render(request, "unsubscribe.html", status_code=404, ok=False, logged_in=False)
    vendor.active = False
    return render(request, "unsubscribe.html", ok=True, logged_in=False)


router.include_router(admin)
