import os
from fastapi import APIRouter, Depends, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from ..db import get_db, SessionLocal
from ..templating import templates
from ..scoring.market import compute_cohort_stats
from ..scoring.engine import rescore_all
from ..scrapers import craigslist as cl
from .. import models, config

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def admin_home(request: Request, db: Session = Depends(get_db)):
    runs = db.execute(
        select(models.ScrapeRun).order_by(desc(models.ScrapeRun.id)).limit(25)
    ).scalars().all()
    stats = db.execute(
        select(models.MarketStat).order_by(desc(models.MarketStat.sample_count)).limit(30)
    ).scalars().all()
    counts = {
        "listings": db.query(models.Listing).count(),
        "active": db.query(models.Listing).filter(models.Listing.status == "active").count(),
        "scores": db.query(models.ListingScore).count(),
    }
    return templates.TemplateResponse(
        "admin.html",
        {"request": request, "runs": runs, "stats": stats, "counts": counts, "config": {
            "metros": config.CRAIGSLIST_METROS,
            "interval_h": config.SCRAPE_INTERVAL_HOURS,
            "ca_op": config.CA_OPERATION,
        }},
    )


@router.post("/scrape")
def run_scrape(bg: BackgroundTasks):
    def _run():
        with SessionLocal() as db:
            cl.run(db)
    bg.add_task(_run)
    return RedirectResponse("/admin/", status_code=303)


@router.post("/rescore")
def run_rescore(bg: BackgroundTasks):
    def _run():
        with SessionLocal() as db:
            compute_cohort_stats(db)
            rescore_all(db)
    bg.add_task(_run)
    return RedirectResponse("/admin/", status_code=303)


@router.get("/backup")
def download_backup():
    # SQLite file path from DATABASE_URL (sqlite:////data/finance.db)
    path = config.DATABASE_URL.split("sqlite:///")[-1] if config.DATABASE_URL.startswith("sqlite") else None
    if not path or not os.path.exists(path):
        return {"ok": False, "error": "db file not found"}
    return FileResponse(path, filename="finance.db", media_type="application/octet-stream")
