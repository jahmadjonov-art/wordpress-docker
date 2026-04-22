import json
from datetime import datetime
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from ..db import get_db
from ..templating import templates
from ..scoring.engine import score_and_save
from .. import models

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def list_listings(
    request: Request,
    category: str | None = None,
    source: str | None = None,
    min_score: int = 0,
    starred: int = 0,
    db: Session = Depends(get_db),
):
    q = select(models.Listing).where(models.Listing.status == "active")
    if category:
        q = q.where(models.Listing.category == category)
    if source:
        q = q.where(models.Listing.source == source)
    if starred:
        q = q.where(models.Listing.user_starred == True)  # noqa: E712
    q = q.order_by(desc(models.Listing.first_seen)).limit(200)
    rows = db.execute(q).scalars().all()

    # filter by score after loading (scores live in a separate table)
    filtered = []
    for r in rows:
        latest = r.scores[0] if r.scores else None
        if latest and latest.score < min_score:
            continue
        filtered.append(r)

    return templates.TemplateResponse(
        "listings/index.html",
        {
            "request": request,
            "rows": filtered,
            "category": category,
            "source": source,
            "min_score": min_score,
            "starred": starred,
        },
    )


@router.get("/manual", response_class=HTMLResponse)
def manual_form(request: Request):
    return templates.TemplateResponse("listings/manual.html", {"request": request, "l": None})


@router.post("/manual")
async def manual_submit(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    listing = _listing_from_form(form)
    listing.fetch_method = "manual"
    listing.source = form.get("source") or "manual"
    if not listing.source_url:
        listing.source_url = f"manual:{datetime.utcnow().isoformat()}"
    db.add(listing)
    db.commit()
    db.refresh(listing)
    score_and_save(db, listing)
    return RedirectResponse(f"/listings/{listing.id}", status_code=303)


@router.get("/{listing_id}", response_class=HTMLResponse)
def listing_detail(listing_id: int, request: Request, db: Session = Depends(get_db)):
    l = db.get(models.Listing, listing_id)
    if not l:
        return templates.TemplateResponse("listings/not_found.html", {"request": request}, status_code=404)
    latest = l.scores[0] if l.scores else None
    breakdown = json.loads(latest.breakdown_json) if latest else []
    return templates.TemplateResponse(
        "listings/detail.html",
        {
            "request": request,
            "l": l,
            "latest": latest,
            "breakdown": breakdown,
            "photos": json.loads(l.photos_json) if l.photos_json else [],
        },
    )


@router.post("/{listing_id}/star")
def toggle_star(listing_id: int, db: Session = Depends(get_db)):
    l = db.get(models.Listing, listing_id)
    if l:
        l.user_starred = not l.user_starred
        db.commit()
    return RedirectResponse(f"/listings/{listing_id}", status_code=303)


@router.post("/{listing_id}/status")
def set_status(listing_id: int, status: str = Form(...), db: Session = Depends(get_db)):
    l = db.get(models.Listing, listing_id)
    if l and status in ("active", "sold", "stale", "flagged"):
        l.status = status
        db.commit()
    return RedirectResponse(f"/listings/{listing_id}", status_code=303)


@router.post("/{listing_id}/notes")
def set_notes(listing_id: int, user_notes: str = Form(""), db: Session = Depends(get_db)):
    l = db.get(models.Listing, listing_id)
    if l:
        l.user_notes = user_notes
        db.commit()
    return RedirectResponse(f"/listings/{listing_id}", status_code=303)


@router.post("/{listing_id}/rescore")
def rescore(listing_id: int, db: Session = Depends(get_db)):
    l = db.get(models.Listing, listing_id)
    if l:
        score_and_save(db, l)
    return RedirectResponse(f"/listings/{listing_id}", status_code=303)


# ---- helpers ----

def _num(form, key, cast=int):
    v = form.get(key)
    if v is None or v == "":
        return None
    try:
        return cast(v)
    except (ValueError, TypeError):
        return None


def _listing_from_form(form) -> models.Listing:
    photos_raw = form.get("photos", "")
    photos = [p.strip() for p in photos_raw.splitlines() if p.strip()]
    price = _num(form, "asking_price", float)
    return models.Listing(
        source=form.get("source") or "manual",
        source_url=form.get("source_url") or "",
        category=form.get("category") or "other",
        title=form.get("title") or "",
        asking_price_cents=int(round(price * 100)) if price is not None else None,
        year=_num(form, "year"),
        make=(form.get("make") or None),
        model=(form.get("model") or None),
        engine=(form.get("engine") or None),
        transmission=(form.get("transmission") or None),
        mileage=_num(form, "mileage"),
        location_city=(form.get("location_city") or None),
        location_state=(form.get("location_state") or None),
        description=(form.get("description") or None),
        photos_json=json.dumps(photos) if photos else None,
        vin=(form.get("vin") or None),
        trailer_length_ft=_num(form, "trailer_length_ft"),
        trailer_door=(form.get("trailer_door") or None),
        trailer_walls=(form.get("trailer_walls") or None),
        trailer_suspension=(form.get("trailer_suspension") or None),
    )
