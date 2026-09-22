"""Routes. Full pages render a template; HTMX requests get a partial (templates/_*.html)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import data
from app.config import settings
from app.identity import Identity, identity_from_request

HERE = Path(__file__).resolve().parent
app = FastAPI(title=settings.title, docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
templates = Jinja2Templates(directory=HERE / "templates")

client: data.DataClient = data.build_client(
    settings.data_api_url, settings.fixtures_dir, settings.name
)

WINDOWS = (30, 60, 90, 180)


def current_identity(request: Request) -> Identity:
    """Who is calling, as established by the platform sign-in (see app/identity.py)."""
    return identity_from_request(request.headers, settings.default_user)


def current_user(request: Request) -> str:
    return current_identity(request).email


def current_caller(request: Request) -> data.Caller:
    """Identity plus the platform token, forwarded to the data API which verifies it."""
    return data.Caller(
        email=current_identity(request).email,
        token=request.headers.get("x-amzn-oidc-accesstoken", ""),
    )


@app.exception_handler(data.DataAccessDenied)
async def data_denied(request: Request, exc: data.DataAccessDenied) -> HTMLResponse:
    """The data API said no. Show exactly why in plain language instead of a stack trace."""
    return templates.TemplateResponse(
        request,
        "data_denied.html",
        {
            "request": request,
            "title": settings.title,
            "user": current_user(request),
            "status": exc.status,
            "detail": exc.detail,
        },
        status_code=exc.status,
    )


@app.middleware("http")
async def enforce_groups(request: Request, call_next):
    """Only members of the groups named in app.yaml (APP_ALLOWED_GROUPS) may use the app.

    Sign-in itself happens at the load balancer; this is the per-app group scope.
    Health checks are exempt so the platform can see the task is alive.
    """
    if request.url.path != "/healthz" and settings.allowed_groups:
        ident = current_identity(request)
        if not set(ident.groups) & set(settings.allowed_groups):
            return templates.TemplateResponse(
                request,
                "forbidden.html",
                {
                    "request": request,
                    "title": settings.title,
                    "user": ident.email,
                    "allowed": settings.allowed_groups,
                },
                status_code=403,
            )
    return await call_next(request)


def _window(value: int | None) -> int:
    return value if value in WINDOWS else 90


def _context(request: Request, within: int, team: str | None) -> dict:
    user = current_caller(request)
    today = date.today()
    rows = data.renewals(client, user, today=today, within_days=within, team=team or None)
    return {
        "request": request,
        "title": settings.title,
        "user": user.email,
        "today": today,
        "within": within,
        "windows": WINDOWS,
        "team": team or "",
        "teams": data.teams(client, user),
        "rows": rows,
        "attention": sum(1 for r in rows if r.tags),
    }


@app.get("/healthz")
def healthz() -> JSONResponse:
    return JSONResponse({"status": "ok", "app": settings.name})


@app.get("/", response_class=HTMLResponse)
def index(request: Request, within: int = 90, team: str = "") -> HTMLResponse:
    return templates.TemplateResponse(
        request, "index.html", _context(request, _window(within), team)
    )


@app.get("/contracts", response_class=HTMLResponse)
def contracts_partial(request: Request, within: int = 90, team: str = "") -> HTMLResponse:
    return templates.TemplateResponse(
        request, "_contracts.html", _context(request, _window(within), team)
    )


@app.post("/contracts/{contract_id}/flag", response_class=HTMLResponse)
def toggle_flag(
    request: Request,
    contract_id: str,
    flagged: bool = Form(...),
    within: int = Form(90),
    team: str = Form(""),
) -> HTMLResponse:
    client.set_flag(current_caller(request), contract_id, flagged)
    return templates.TemplateResponse(
        request, "_contracts.html", _context(request, _window(within), team)
    )


@app.get("/whoami", response_class=HTMLResponse)
def whoami(request: Request) -> HTMLResponse:
    """Who am I, and what can this app see on my behalf? Answered by the data API."""
    ident = current_identity(request)
    info = client.whoami(current_caller(request))
    return templates.TemplateResponse(
        request,
        "whoami.html",
        {
            "request": request,
            "title": settings.title,
            "user": ident.email,
            "groups": ident.groups,
            "info": info,
            "allowed": settings.allowed_groups,
        },
    )
