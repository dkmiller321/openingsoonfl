"""Vendor management (V1-V3)."""

import re
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from osfl import clock
from osfl.db import DbSession
from osfl.models import Category, Vendor
from osfl.settings import SUPPORTED_COUNTIES, get_settings
from osfl.web.common import flash, render, require_login

router = APIRouter(dependencies=[Depends(require_login)])

EMAIL_RE = re.compile(r"^[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+$")


def _categories(session: Session) -> list[Category]:
    return list(session.scalars(select(Category).order_by(Category.position)))


@router.get("/vendors")
def vendor_list(request: Request, session: DbSession):
    vendors = session.execute(
        select(Vendor, Category.name)
        .join(Category, Category.id == Vendor.category_id)
        .order_by(Vendor.name, Vendor.id)
    ).all()
    return render(request, "vendors.html", active="vendors", vendors=vendors)


def _form_page(request: Request, session: Session, vendor: dict, error: str | None,
               vendor_id: int | None):
    return render(
        request, "vendor_form.html", active="vendors", v=vendor, error=error,
        vendor_id=vendor_id, categories=_categories(session), counties=SUPPORTED_COUNTIES,
        status_code=422 if error else 200,
    )


@router.get("/vendors/new")
def vendor_new(request: Request, session: DbSession):
    blank = {"name": "", "emails": "", "category_id": None, "counties": ["brevard"],
             "cadence": "weekly", "active": True}
    return _form_page(request, session, blank, None, None)


@router.get("/vendors/{vendor_id}")
def vendor_edit(vendor_id: int, request: Request, session: DbSession):
    vendor = session.get(Vendor, vendor_id)
    if vendor is None:
        raise HTTPException(404, "Vendor not found")
    values = {"name": vendor.name, "emails": ", ".join(vendor.emails),
              "category_id": vendor.category_id, "counties": vendor.counties,
              "cadence": vendor.cadence, "active": vendor.active}
    return _form_page(request, session, values, None, vendor_id)


def _validate(values: dict, session: Session) -> tuple[dict | None, str | None]:
    emails = [e for e in re.split(r"[,\s;]+", values["emails"]) if e]
    if not values["name"]:
        return None, "Enter a name"
    if not emails or not all(EMAIL_RE.match(e) for e in emails):
        return None, "Enter valid email addresses"
    category = session.get(Category, values["category_id"]) if values["category_id"] else None
    if category is None:
        return None, "Pick a category"
    counties = [c for c in values["counties"] if c in SUPPORTED_COUNTIES]
    if not counties:
        return None, "Pick at least one county"
    if values["cadence"] not in ("weekly", "daily"):
        return None, "Pick weekly or daily"
    return {"name": values["name"], "emails": [e.lower() for e in emails],
            "category_id": category.id, "counties": counties,
            "cadence": values["cadence"], "active": values["active"]}, None


async def _read_form(request: Request) -> dict:
    form = await request.form()
    category = str(form.get("category_id") or "")
    return {
        "name": str(form.get("name") or "").strip(),
        "emails": str(form.get("emails") or "").strip(),
        "category_id": int(category) if category.isdigit() else None,
        "counties": [str(c) for c in form.getlist("counties")],
        "cadence": str(form.get("cadence") or "weekly"),
        "active": form.get("active") == "1",
    }


@router.post("/vendors/new")
async def vendor_create(request: Request, session: DbSession):
    values = await _read_form(request)
    clean, error = _validate(values, session)
    if error or clean is None:
        return _form_page(request, session, values, error, None)
    vendor = Vendor(**clean, unsubscribe_token=secrets.token_urlsafe(16), created_at=clock.now())
    session.add(vendor)
    session.flush()
    _cap_warning(request, session, vendor)
    return RedirectResponse("/vendors", status_code=303)


@router.post("/vendors/{vendor_id}")
async def vendor_update(vendor_id: int, request: Request, session: DbSession):
    vendor = session.get(Vendor, vendor_id)
    if vendor is None:
        raise HTTPException(404, "Vendor not found")
    values = await _read_form(request)
    clean, error = _validate(values, session)
    if error or clean is None:
        return _form_page(request, session, values, error, vendor_id)
    for key, value in clean.items():
        setattr(vendor, key, value)
    session.flush()
    _cap_warning(request, session, vendor)
    return RedirectResponse("/vendors", status_code=303)


def _cap_warning(request: Request, session: Session, vendor: Vendor) -> None:
    """V3: warn, don't block, when a category already has the cap of active vendors."""
    if not vendor.active:
        return
    cap = get_settings().max_vendors_per_category
    category = session.get(Category, vendor.category_id)
    assert category is not None
    for county in vendor.counties:
        others = session.scalar(
            select(func.count()).select_from(Vendor).where(
                Vendor.id != vendor.id,
                Vendor.active.is_(True),
                Vendor.category_id == vendor.category_id,
                Vendor.counties.any(county),
            )
        ) or 0
        if others >= cap:
            flash(request, "cap",
                  f"{category.name} already has {others} active vendors in {county.title()}")
