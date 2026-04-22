import csv
import io
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from ..db import get_db
from .. import models

router = APIRouter()


def _csv_response(rows, header, filename):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    for r in rows:
        w.writerow(r)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/income.csv")
def export_income(db: Session = Depends(get_db)):
    rows = db.execute(select(models.IncomeEntry).order_by(desc(models.IncomeEntry.week_ending))).scalars().all()
    return _csv_response(
        [[r.week_ending, r.gross_cents / 100, (r.net_cents or 0) / 100, r.miles or "", r.source, r.notes or ""] for r in rows],
        ["week_ending", "gross", "net", "miles", "source", "notes"],
        "income.csv",
    )


@router.get("/expenses.csv")
def export_expenses(db: Session = Depends(get_db)):
    rows = db.execute(select(models.ExpenseEntry).order_by(desc(models.ExpenseEntry.month))).scalars().all()
    return _csv_response(
        [[r.month, r.category, r.amount_cents / 100, r.notes or ""] for r in rows],
        ["month", "category", "amount", "notes"],
        "expenses.csv",
    )


@router.get("/listings.csv")
def export_listings(db: Session = Depends(get_db)):
    rows = db.execute(select(models.Listing).order_by(desc(models.Listing.first_seen))).scalars().all()
    out = []
    for l in rows:
        latest = l.scores[0] if l.scores else None
        out.append([
            l.id, l.source, l.category, l.title, l.year or "", l.make or "", l.model or "",
            l.engine or "", l.mileage or "", (l.asking_price_cents or 0) / 100,
            latest.score if latest else "", l.status, l.source_url,
        ])
    return _csv_response(
        out,
        ["id", "source", "category", "title", "year", "make", "model", "engine", "mileage", "price", "score", "status", "url"],
        "listings.csv",
    )
