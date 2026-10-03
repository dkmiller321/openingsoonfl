"""Admin console routes: login/logout here; page modules register theirs on `router`."""

import secrets

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from osfl.settings import get_settings
from osfl.web.common import render

router = APIRouter()


@router.get("/login")
def login_page(request: Request):
    return render(request, "login.html", error=None, logged_in=False)


@router.post("/login")
def login_submit(request: Request, password: str = Form("")):
    expected = get_settings().admin_password
    if not secrets.compare_digest(password.encode(), expected.encode()):
        return render(
            request, "login.html", status_code=401, error="Wrong password", logged_in=False
        )
    request.session.clear()
    request.session["admin"] = True
    return RedirectResponse("/", status_code=303)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


from osfl.web import digests, leads, vendors  # noqa: E402

router.include_router(leads.router)
router.include_router(vendors.router)
router.include_router(digests.router)
