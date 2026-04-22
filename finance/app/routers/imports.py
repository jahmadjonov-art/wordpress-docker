import json
from datetime import datetime
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..templating import templates
from ..scrapers.paste import fetch_and_parse
from ..scoring.engine import score_and_save
from .. import models

router = APIRouter()


@router.get("/import", response_class=HTMLResponse)
def import_form(request: Request):
    return templates.TemplateResponse(
        "listings/import.html",
        {"request": request, "preview": None, "error": None, "url": ""},
    )


@router.post("/import/preview", response_class=HTMLResponse)
async def import_preview(request: Request, url: str = Form(...)):
    try:
        data = fetch_and_parse(url)
        return templates.TemplateResponse(
            "listings/import.html",
            {"request": request, "preview": data, "error": None, "url": url},
        )
    except Exception as e:
        return templates.TemplateResponse(
            "listings/import.html",
            {
                "request": request,
                "preview": None,
                "error": (
                    f"Could not fetch {url} — {type(e).__name__}: {e}. "
                    f"FB Marketplace and some paywalled sites block bots; "
                    f"use the Manual form and copy-paste the listing text."
                ),
                "url": url,
            },
        )


@router.post("/import/confirm")
async def import_confirm(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    url = form.get("source_url") or ""
    # dedupe
    existing = db.execute(select(models.Listing).where(models.Listing.source_url == url)).scalar_one_or_none()
    if existing:
        existing.last_seen = datetime.utcnow()
        db.commit()
        return RedirectResponse(f"/listings/{existing.id}", status_code=303)

    photos_raw = form.get("photos", "")
    photos = [p.strip() for p in photos_raw.splitlines() if p.strip()]
    price = form.get("asking_price") or ""
    try:
        price_cents = int(round(float(price) * 100)) if price else None
    except ValueError:
        price_cents = None

    def _intnull(k):
        v = form.get(k) or ""
        try:
            return int(v) if v else None
        except ValueError:
            return None

    listing = models.Listing(
        source=form.get("source") or "manual",
        source_url=url or f"manual:{datetime.utcnow().isoformat()}",
        category=form.get("category") or "other",
        title=form.get("title") or url,
        asking_price_cents=price_cents,
        year=_intnull("year"),
        make=form.get("make") or None,
        model=form.get("model") or None,
        engine=form.get("engine") or None,
        transmission=form.get("transmission") or None,
        mileage=_intnull("mileage"),
        vin=form.get("vin") or None,
        description=form.get("description") or None,
        photos_json=json.dumps(photos) if photos else None,
        trailer_length_ft=_intnull("trailer_length_ft"),
        trailer_door=form.get("trailer_door") or None,
        trailer_walls=form.get("trailer_walls") or None,
        trailer_suspension=form.get("trailer_suspension") or None,
        fetch_method=form.get("fetch_method") or "paste",
    )
    db.add(listing)
    db.commit()
    db.refresh(listing)
    score_and_save(db, listing)
    return RedirectResponse(f"/listings/{listing.id}", status_code=303)
