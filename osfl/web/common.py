"""Shared web helpers: templates, the login requirement, flash messages."""

from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from osfl.formatting import days_ahead_label, lead_type_label, long_date
from osfl.web.appearance import PALETTES, THEMES, appearance

TEMPLATES = Jinja2Templates(directory=Path(__file__).parent / "templates")
TEMPLATES.env.filters["lead_type_label"] = lead_type_label
TEMPLATES.env.filters["days_ahead_label"] = days_ahead_label
TEMPLATES.env.filters["long_date"] = long_date


class LoginRequired(Exception):
    """Raised by `require_login`; the app turns it into a redirect to /login."""


def require_login(request: Request) -> None:
    if not request.session.get("admin"):
        raise LoginRequired()


def flash(request: Request, kind: str, message: str) -> None:
    request.session.setdefault("flash", []).append({"kind": kind, "message": message})


def pop_flash(request: Request) -> list[dict[str, str]]:
    return request.session.pop("flash", [])


def render(request: Request, template: str, status_code: int = 200, **context: Any) -> HTMLResponse:
    context.setdefault("logged_in", bool(request.session.get("admin")))
    context["theme"], context["palette"] = appearance(request)
    context.setdefault("themes", THEMES)
    context.setdefault("palettes", PALETTES)
    context.setdefault("flashes", pop_flash(request))
    return TEMPLATES.TemplateResponse(request, template, context, status_code=status_code)
