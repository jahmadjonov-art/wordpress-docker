import json
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from ..db import get_db
from ..templating import templates
from ..summary import summary
from .. import models, config

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def view_goal(request: Request, db: Session = Depends(get_db)):
    goal = db.get(models.SavingsGoal, 1)
    s = summary(db)
    return templates.TemplateResponse(
        "goal.html",
        {
            "request": request,
            "goal": goal,
            "buckets": json.loads(goal.buckets_json) if goal else [],
            "summary": s,
            "defaults": config.DEFAULT_BUCKETS,
        },
    )


@router.post("/")
async def update_goal(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    names = form.getlist("bucket_name")
    targets = form.getlist("bucket_target")
    currents = form.getlist("bucket_current")
    buckets = []
    for name, target, current in zip(names, targets, currents):
        if not name.strip():
            continue
        buckets.append(
            {
                "name": name.strip(),
                "target_cents": int(round(float(target or 0) * 100)),
                "current_cents": int(round(float(current or 0) * 100)),
            }
        )
    total = sum(b["target_cents"] for b in buckets)
    goal = db.get(models.SavingsGoal, 1)
    if goal is None:
        goal = models.SavingsGoal(id=1, target_cents=total, buckets_json=json.dumps(buckets))
        db.add(goal)
    else:
        goal.target_cents = total
        goal.buckets_json = json.dumps(buckets)
    db.commit()
    return RedirectResponse("/goal/", status_code=303)
