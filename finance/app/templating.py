from pathlib import Path
from fastapi.templating import Jinja2Templates

BASE = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE / "templates"))


def _fmt_money(cents) -> str:
    if cents is None:
        return "—"
    neg = cents < 0
    cents = abs(int(cents))
    dollars = cents / 100
    if dollars >= 10000:
        s = f"${dollars:,.0f}"
    else:
        s = f"${dollars:,.2f}"
    return f"-{s}" if neg else s


def _fmt_miles(n) -> str:
    if n is None:
        return "—"
    return f"{int(n):,}"


templates.env.filters["money"] = _fmt_money
templates.env.filters["miles"] = _fmt_miles
