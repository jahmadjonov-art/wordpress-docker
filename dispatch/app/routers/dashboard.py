from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select, desc, func
from sqlalchemy.orm import Session

from ..db import get_db
from ..templating import templates
from ..integrations import eia
from .. import models

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    active = db.execute(
        select(models.Load).where(models.Load.status == "active")
        .order_by(desc(models.Load.created_at)).limit(8)
    ).scalars().all()

    total_active = db.scalar(
        select(func.count()).select_from(models.Load).where(models.Load.status == "active")
    ) or 0
    booked = db.scalar(
        select(func.count()).select_from(models.Load).where(models.Load.status == "booked")
    ) or 0
    lanes = db.scalar(select(func.count()).select_from(models.LaneStat)) or 0

    # best load by latest score among the recent ones
    def latest_score(l):
        return l.scores[0].score if l.scores else -1
    best = max(active, key=latest_score, default=None)

    diesel_cpg = eia.current_cpg(db)

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "recent": active,
            "total_active": total_active,
            "booked": booked,
            "lanes": lanes,
            "best": best if best and latest_score(best) >= 0 else None,
            "diesel_cpg": diesel_cpg,
            "latest_score": latest_score,
        },
    )
