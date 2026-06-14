import csv
import io
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from ..db import get_db
from .. import models

router = APIRouter()


@router.get("/loads.csv")
def export_loads(db: Session = Depends(get_db)):
    rows = db.execute(
        select(models.Load).order_by(desc(models.Load.created_at))
    ).scalars().all()

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        "id", "origin", "dest", "equipment", "loaded_miles", "deadhead_miles",
        "miles_source", "rate_total", "rate_per_mile", "score", "est_cost",
        "est_profit", "suggested_target_rate", "broker_name", "broker_mc", "status",
    ])
    for l in rows:
        s = l.scores[0] if l.scores else None
        w.writerow([
            l.id,
            f"{l.origin_city}, {l.origin_state}",
            f"{l.dest_city}, {l.dest_state}",
            l.equipment,
            l.loaded_miles or "",
            l.deadhead_miles or 0,
            l.miles_source,
            f"{l.rate_total_cents/100:.2f}" if l.rate_total_cents else "",
            f"{l.rate_per_mile_cents/100:.2f}" if l.rate_per_mile_cents else "",
            s.score if s else "",
            f"{s.est_cost_cents/100:.2f}" if s and s.est_cost_cents else "",
            f"{s.est_profit_cents/100:.2f}" if s and s.est_profit_cents is not None else "",
            f"{s.suggested_target_rate_cents/100:.2f}" if s and s.suggested_target_rate_cents else "",
            l.broker_name or "",
            l.broker_mc or "",
            l.status,
        ])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=loads.csv"},
    )
