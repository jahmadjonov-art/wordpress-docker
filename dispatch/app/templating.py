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
    return f"{int(round(n)):,}"


def _fmt_rpm(cents) -> str:
    """Rate-per-mile, shown in dollars with cents (e.g. $2.18)."""
    if cents is None:
        return "—"
    return f"${cents / 100:.2f}"


templates.env.filters["money"] = _fmt_money
templates.env.filters["miles"] = _fmt_miles
templates.env.filters["rpm"] = _fmt_rpm
