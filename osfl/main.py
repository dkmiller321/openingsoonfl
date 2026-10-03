"""App factory: settings are validated first, so a bad config stops startup with a clear message."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from osfl.db import db_ok, session_scope
from osfl.seed import ensure_categories
from osfl.settings import get_settings

STATIC_DIR = Path(__file__).parent / "web" / "static"


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
        with session_scope() as session:
            ensure_categories(session)
        scheduler = None
        if settings.scheduler_enabled:
            from osfl.scheduler import start_scheduler

            scheduler = start_scheduler()
        yield
        if scheduler is not None:
            scheduler.shutdown(wait=False)

    app = FastAPI(title="OpeningSoon FL", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        session_cookie="osfl_session",
        https_only=settings.app_base_url.startswith("https://"),
        same_site="lax",
    )
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/health")
    def health() -> JSONResponse:
        ok = db_ok()
        body = {"status": "ok" if ok else "error", "db": "ok" if ok else "error"}
        return JSONResponse(body, status_code=200 if ok else 503)

    from osfl.web.common import LoginRequired
    from osfl.web.routes import router as web_router

    @app.exception_handler(LoginRequired)
    def _to_login(request: Request, exc: LoginRequired) -> RedirectResponse:
        return RedirectResponse("/login", status_code=303)

    app.include_router(web_router)

    if settings.test_routes:
        from osfl.testing.routes import router as test_router

        app.include_router(test_router)

    return app


app = create_app()
