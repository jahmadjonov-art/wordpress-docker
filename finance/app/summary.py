"""Cross-router aggregations for savings + burn rate + ETA."""
import json
from datetime import date, timedelta
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models


def current_balance_cents(db: Session) -> int:
    income = db.execute(select(func.coalesce(func.sum(models.IncomeEntry.net_cents), 0))).scalar() or 0
    if income == 0:
        income = db.execute(select(func.coalesce(func.sum(models.IncomeEntry.gross_cents), 0))).scalar() or 0
    expenses = db.execute(select(func.coalesce(func.sum(models.ExpenseEntry.amount_cents), 0))).scalar() or 0
    return int(income) - int(expenses)


def recent_weekly_avg_income(db: Session, weeks: int = 8) -> int:
    cutoff = date.today() - timedelta(weeks=weeks)
    rows = db.execute(
        select(models.IncomeEntry).where(models.IncomeEntry.week_ending >= cutoff)
    ).scalars().all()
    if not rows:
        return 0
    total = sum((r.net_cents or r.gross_cents or 0) for r in rows)
    return total // max(len(rows), 1)


def recent_monthly_avg_expenses(db: Session, months: int = 3) -> int:
    rows = db.execute(select(models.ExpenseEntry)).scalars().all()
    if not rows:
        return 0
    by_month: dict[str, int] = {}
    for r in rows:
        by_month[r.month] = by_month.get(r.month, 0) + r.amount_cents
    recent = sorted(by_month.items())[-months:]
    if not recent:
        return 0
    return sum(v for _, v in recent) // len(recent)


def summary(db: Session) -> dict:
    goal = db.get(models.SavingsGoal, 1)
    buckets = json.loads(goal.buckets_json) if goal else []
    target_cents = goal.target_cents if goal else 0
    balance = current_balance_cents(db)
    weekly_income = recent_weekly_avg_income(db)
    monthly_expense = recent_monthly_avg_expenses(db)
    weekly_expense = monthly_expense * 12 // 52
    weekly_save = max(weekly_income - weekly_expense, 0)
    remaining = max(target_cents - balance, 0)
    weeks_to_goal = (remaining / weekly_save) if weekly_save > 0 else None
    progress_pct = min(100, int(balance * 100 / target_cents)) if target_cents else 0
    return {
        "balance_cents": balance,
        "target_cents": target_cents,
        "remaining_cents": remaining,
        "progress_pct": progress_pct,
        "weekly_income_cents": weekly_income,
        "monthly_expense_cents": monthly_expense,
        "weekly_save_cents": weekly_save,
        "weeks_to_goal": weeks_to_goal,
        "buckets": buckets,
    }


def savings_curve_points(db: Session, weeks: int = 26) -> list[tuple[str, int]]:
    """Weekly savings points for the dashboard sparkline."""
    today = date.today()
    start = today - timedelta(weeks=weeks)
    incomes = db.execute(
        select(models.IncomeEntry).where(models.IncomeEntry.week_ending >= start)
    ).scalars().all()
    expenses = db.execute(select(models.ExpenseEntry)).scalars().all()

    by_week: dict[date, int] = {}
    for inc in incomes:
        by_week[inc.week_ending] = by_week.get(inc.week_ending, 0) + (inc.net_cents or inc.gross_cents or 0)

    # expenses monthly -> spread evenly across weeks of that month
    for exp in expenses:
        try:
            y, m = [int(x) for x in exp.month.split("-")]
        except Exception:
            continue
        weekly_share = exp.amount_cents // 4
        for w in range(4):
            d = date(y, m, min(1 + 7 * w, 28))
            if d >= start:
                by_week[d] = by_week.get(d, 0) - weekly_share

    cum = 0
    points: list[tuple[str, int]] = []
    for d in sorted(by_week.keys()):
        cum += by_week[d]
        points.append((d.isoformat(), cum))
    return points
