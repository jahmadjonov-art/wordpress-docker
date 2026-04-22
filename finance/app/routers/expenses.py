from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from ..db import get_db
from ..templating import templates
from .. import models

router = APIRouter()

CATEGORIES = [
    "food", "phone", "personal_insurance", "medical", "clothing",
    "truck_parking", "supplies", "gifts_home", "misc",
]


@router.get("/", response_class=HTMLResponse)
def list_expenses(request: Request, db: Session = Depends(get_db)):
    rows = db.execute(
        select(models.ExpenseEntry).order_by(desc(models.ExpenseEntry.month), desc(models.ExpenseEntry.id)).limit(500)
    ).scalars().all()
    return templates.TemplateResponse(
        "expenses.html",
        {"request": request, "rows": rows, "categories": CATEGORIES},
    )


@router.post("/")
def add_expense(
    month: str = Form(...),
    category: str = Form(...),
    amount: float = Form(...),
    notes: str | None = Form(None),
    db: Session = Depends(get_db),
):
    db.add(
        models.ExpenseEntry(
            month=month,
            category=category,
            amount_cents=int(round(amount * 100)),
            notes=notes,
        )
    )
    db.commit()
    return RedirectResponse("/expenses/", status_code=303)


@router.post("/{entry_id}/delete")
def delete_expense(entry_id: int, db: Session = Depends(get_db)):
    row = db.get(models.ExpenseEntry, entry_id)
    if row:
        db.delete(row)
        db.commit()
    return RedirectResponse("/expenses/", status_code=303)
