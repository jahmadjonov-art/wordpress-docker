from datetime import date, datetime
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from ..db import get_db
from ..templating import templates
from .. import models

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def list_income(request: Request, db: Session = Depends(get_db)):
    rows = db.execute(
        select(models.IncomeEntry).order_by(desc(models.IncomeEntry.week_ending)).limit(200)
    ).scalars().all()
    return templates.TemplateResponse("income.html", {"request": request, "rows": rows})


@router.post("/")
def add_income(
    week_ending: str = Form(...),
    gross: float = Form(...),
    net: float | None = Form(None),
    miles: int | None = Form(None),
    source: str = Form("W-2 company driver"),
    notes: str | None = Form(None),
    db: Session = Depends(get_db),
):
    db.add(
        models.IncomeEntry(
            week_ending=datetime.strptime(week_ending, "%Y-%m-%d").date(),
            gross_cents=int(round(gross * 100)),
            net_cents=int(round(net * 100)) if net is not None else None,
            miles=miles,
            source=source,
            notes=notes,
        )
    )
    db.commit()
    return RedirectResponse("/income/", status_code=303)


@router.post("/{entry_id}/delete")
def delete_income(entry_id: int, db: Session = Depends(get_db)):
    row = db.get(models.IncomeEntry, entry_id)
    if row:
        db.delete(row)
        db.commit()
    return RedirectResponse("/income/", status_code=303)
