from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from .db import init_db
from .deps import require_auth
from .routers import dashboard, loads, settings, exports

BASE = Path(__file__).resolve().parent

app = FastAPI(title="Freight Dispatcher — LoadScorer", docs_url=None, redoc_url=None)


@app.on_event("startup")
def _startup():
    init_db()


app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")

_auth = [Depends(require_auth)]

app.include_router(dashboard.router, dependencies=_auth)
app.include_router(loads.router, prefix="/loads", dependencies=_auth)
app.include_router(settings.router, prefix="/settings", dependencies=_auth)
app.include_router(exports.router, prefix="/export", dependencies=_auth)


@app.get("/healthz")
def healthz():
    return {"ok": True}
