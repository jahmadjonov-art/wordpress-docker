from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from . import config
from .db import init_db
from .engine import StockfishEngine
from .routers import game

BASE = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    app.state.engine = StockfishEngine(config.ENGINE_PATH)
    app.state.engine.start()
    try:
        yield
    finally:
        app.state.engine.close()


app = FastAPI(title="Chess Teaching Bot", docs_url=None, redoc_url=None, lifespan=lifespan)

app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")
app.include_router(game.router)


@app.get("/healthz")
def healthz():
    return {"ok": True}
