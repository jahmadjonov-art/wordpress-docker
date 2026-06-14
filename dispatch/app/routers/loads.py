import json
from datetime import datetime, date
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from ..db import get_db
from ..templating import templates
from ..scoring.engine import score_and_save
from ..scoring import broker_rating, backhaul
from ..integrations import routing, fmcsa
from ..ai import negotiate
from .. import models, config

router = APIRouter()


# ---------------- list ----------------

@router.get("/", response_class=HTMLResponse)
def list_loads(
    request: Request,
    equipment: str | None = None,
    min_score: int = 0,
    starred: int = 0,
    db: Session = Depends(get_db),
):
    q = select(models.Load).where(models.Load.status == "active")
    if equipment:
        q = q.where(models.Load.equipment == equipment)
    if starred:
        q = q.where(models.Load.user_starred == True)  # noqa: E712
    q = q.order_by(desc(models.Load.created_at)).limit(200)
    rows = db.execute(q).scalars().all()

    filtered = []
    for r in rows:
        latest = r.scores[0] if r.scores else None
        if latest and latest.score < min_score:
            continue
        filtered.append(r)

    return templates.TemplateResponse(
        "loads/index.html",
        {
            "request": request,
            "rows": filtered,
            "equipment": equipment,
            "min_score": min_score,
            "starred": starred,
            "equipment_types": config.EQUIPMENT_TYPES,
        },
    )


# ---------------- new / create ----------------

@router.get("/new", response_class=HTMLResponse)
def new_form(request: Request):
    return templates.TemplateResponse(
        "loads/new.html",
        {"request": request, "equipment_types": config.EQUIPMENT_TYPES},
    )


@router.post("/new")
async def create_load(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    load = _load_from_form(form)
    db.add(load)
    db.commit()
    db.refresh(load)

    _resolve_route(load)        # geocode + miles + rate-per-mile
    db.commit()

    score_and_save(db, load)
    return RedirectResponse(f"/loads/{load.id}", status_code=303)


# ---------------- detail ----------------

@router.get("/{load_id}", response_class=HTMLResponse)
def load_detail(load_id: int, request: Request, db: Session = Depends(get_db)):
    load = db.get(models.Load, load_id)
    if not load:
        return templates.TemplateResponse("loads/not_found.html", {"request": request}, status_code=404)
    latest = load.scores[0] if load.scores else None
    breakdown = json.loads(latest.breakdown_json) if latest else []

    backhauls = backhaul.find_backhauls(db, load)
    best_round_trip = backhaul.round_trip(load, backhauls[0]) if backhauls else None

    broker = None
    if load.broker_mc:
        broker = db.execute(
            select(models.Broker).where(models.Broker.mc_number == fmcsa._clean_mc(load.broker_mc))
        ).scalar_one_or_none()
    return templates.TemplateResponse(
        "loads/detail.html",
        {
            "request": request,
            "l": load,
            "latest": latest,
            "breakdown": breakdown,
            "broker": broker,
            "broker_label": broker_rating.label(broker.reliability_elo) if broker else None,
            "backhauls": backhauls,
            "best_round_trip": best_round_trip,
            "fmcsa_configured": fmcsa.configured(),
            "ai_configured": negotiate.configured(),
        },
    )


# ---------------- actions ----------------

@router.post("/{load_id}/star")
def toggle_star(load_id: int, db: Session = Depends(get_db)):
    load = db.get(models.Load, load_id)
    if load:
        load.user_starred = not load.user_starred
        db.commit()
    return RedirectResponse(f"/loads/{load_id}", status_code=303)


@router.post("/{load_id}/status")
def set_status(load_id: int, status: str = Form(...), db: Session = Depends(get_db)):
    load = db.get(models.Load, load_id)
    if load and status in ("active", "booked", "passed"):
        load.status = status
        db.commit()
    return RedirectResponse(f"/loads/{load_id}", status_code=303)


@router.post("/{load_id}/rescore")
def rescore(load_id: int, db: Session = Depends(get_db)):
    load = db.get(models.Load, load_id)
    if load:
        _resolve_route(load)
        db.commit()
        score_and_save(db, load)
    return RedirectResponse(f"/loads/{load_id}", status_code=303)


@router.post("/{load_id}/letter")
def make_letter(load_id: int, db: Session = Depends(get_db)):
    load = db.get(models.Load, load_id)
    if load and negotiate.configured():
        latest = load.scores[0] if load.scores else None
        try:
            text = negotiate.generate_letter(load, latest)
            load.letter_text = text
            load.letter_generated_at = datetime.utcnow()
            db.commit()
        except Exception as e:  # surface API errors rather than 500
            load.letter_text = f"[Could not generate letter: {type(e).__name__}: {e}]"
            db.commit()
    return RedirectResponse(f"/loads/{load_id}", status_code=303)


@router.post("/{load_id}/outcome")
async def log_outcome(load_id: int, request: Request, db: Session = Depends(get_db)):
    """Record how a completed load went; updates the broker's reliability Elo."""
    load = db.get(models.Load, load_id)
    if not load:
        return RedirectResponse("/loads/", status_code=303)
    form = await request.form()

    paid_timing = form.get("paid_timing") or "on_time"
    detention = form.get("detention_honored") or "na"
    rate_accurate = form.get("rate_accurate") or "na"
    tonu = form.get("tonu") == "1"
    margin_pct = _num(form, "margin_pct", float)

    delta = broker_rating.outcome_delta(paid_timing, detention, rate_accurate, tonu)

    db.add(models.LoadOutcome(
        load_id=load.id, broker_mc=fmcsa._clean_mc(load.broker_mc or "") or None,
        paid_timing=paid_timing, detention_honored=detention, rate_accurate=rate_accurate,
        tonu=tonu, margin_pct=margin_pct, elo_delta=delta,
        notes=(form.get("outcome_notes") or None),
    ))

    if load.broker_mc:
        broker = _get_or_create_broker(db, load.broker_mc, load.broker_name)
        broker.reliability_elo = broker_rating.apply(broker.reliability_elo, delta)
        broker.outcomes_count = (broker.outcomes_count or 0) + 1
        if margin_pct is not None:
            n = broker.outcomes_count
            prev = broker.avg_margin_pct if broker.avg_margin_pct is not None else margin_pct
            broker.avg_margin_pct = (prev * (n - 1) + margin_pct) / n
    db.commit()

    # re-score so the new reliability flows into the load score
    score_and_save(db, load)
    return RedirectResponse(f"/loads/{load_id}", status_code=303)


# ---------------- helpers ----------------

def _get_or_create_broker(db, mc_number: str, name: str | None) -> models.Broker:
    mc = fmcsa._clean_mc(mc_number)
    broker = db.execute(
        select(models.Broker).where(models.Broker.mc_number == mc)
    ).scalar_one_or_none()
    if broker is None:
        broker = models.Broker(mc_number=mc, legal_name=name)
        db.add(broker)
        db.flush()
    return broker


def _num(form, key, cast=int):
    v = form.get(key)
    if v is None or v == "":
        return None
    try:
        return cast(v)
    except (ValueError, TypeError):
        return None


def _load_from_form(form) -> models.Load:
    rate = _num(form, "rate_total", float)
    pickup = None
    if form.get("pickup_date"):
        try:
            pickup = date.fromisoformat(form.get("pickup_date"))
        except ValueError:
            pickup = None
    equipment = (form.get("equipment") or "van").lower()
    if equipment not in config.EQUIPMENT_TYPES:
        equipment = "van"
    manual_miles = _num(form, "loaded_miles", float)  # optional override of routed miles
    return models.Load(
        source="manual",
        origin_city=(form.get("origin_city") or "").strip(),
        origin_state=(form.get("origin_state") or "").strip().upper(),
        dest_city=(form.get("dest_city") or "").strip(),
        dest_state=(form.get("dest_state") or "").strip().upper(),
        equipment=equipment,
        weight_lbs=_num(form, "weight_lbs"),
        commodity=(form.get("commodity") or None),
        pickup_date=pickup,
        deadhead_miles=_num(form, "deadhead_miles", float) or 0.0,
        loaded_miles=manual_miles,
        miles_source="manual" if manual_miles else "none",
        rate_total_cents=int(round(rate * 100)) if rate is not None else None,
        broker_name=(form.get("broker_name") or None),
        broker_mc=(form.get("broker_mc") or None),
        lumper_fee_cents=(lambda v: int(round(v * 100)) if v is not None else None)(_num(form, "lumper_fee", float)),
        payment_terms=(form.get("payment_terms") or None),
        notes=(form.get("notes") or None),
    )


def _resolve_route(load: models.Load) -> None:
    """Geocode endpoints (if needed), compute loaded miles, derive rate/mile.

    A user-entered mileage (miles_source == "manual") is always respected.
    """
    if load.origin_lat is None:
        coords = routing.geocode(load.origin_city, load.origin_state)
        if coords:
            load.origin_lat, load.origin_lng = coords
    if load.dest_lat is None:
        coords = routing.geocode(load.dest_city, load.dest_state)
        if coords:
            load.dest_lat, load.dest_lng = coords

    if load.miles_source != "manual" and load.origin_lat is not None and load.dest_lat is not None:
        miles, source = routing.road_miles(
            (load.origin_lat, load.origin_lng), (load.dest_lat, load.dest_lng)
        )
        load.loaded_miles = round(miles, 1)
        load.miles_source = source

    # derive rate-per-mile from loaded miles
    if load.rate_total_cents and load.loaded_miles:
        load.rate_per_mile_cents = int(round(load.rate_total_cents / load.loaded_miles))
    else:
        load.rate_per_mile_cents = None
