from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

from .db import init_db
from .deps import require_auth
from .routers import dashboard, income, expenses, goal, listings, imports, admin, exports

BASE = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE / "templates"))

app = FastAPI(title="Trucker Finance & Deal Scorer", docs_url=None, redoc_url=None)


@app.on_event("startup")
def _startup():
    init_db()


app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")

_auth = [Depends(require_auth)]

app.include_router(dashboard.router, dependencies=_auth)
app.include_router(income.router, prefix="/income", dependencies=_auth)
app.include_router(expenses.router, prefix="/expenses", dependencies=_auth)
app.include_router(goal.router, prefix="/goal", dependencies=_auth)
app.include_router(imports.router, prefix="/listings", dependencies=_auth)
app.include_router(listings.router, prefix="/listings", dependencies=_auth)
app.include_router(admin.router, prefix="/admin", dependencies=_auth)
app.include_router(exports.router, prefix="/export", dependencies=_auth)


@app.get("/healthz")
def healthz():
    return {"ok": True}
