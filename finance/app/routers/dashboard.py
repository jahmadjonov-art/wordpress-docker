from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from ..db import get_db
from ..templating import templates
from ..summary import summary, savings_curve_points
from .. import models

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    s = summary(db)
    points = savings_curve_points(db)
    top_deals = (
        db.execute(
            select(models.Listing)
            .join(models.ListingScore, models.Listing.id == models.ListingScore.listing_id)
            .where(models.Listing.status == "active")
            .order_by(desc(models.ListingScore.score))
            .limit(5)
        )
        .scalars()
        .unique()
        .all()
    )
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "summary": s,
            "curve": points,
            "top_deals": top_deals,
        },
    )
