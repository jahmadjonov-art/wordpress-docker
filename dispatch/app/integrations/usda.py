"""USDA AMS produce truck-rate seed (best-effort, graceful).

Pulls a USDA MyMarketNews truck-rate report and stores a national reference
rate-per-mile that the cold-start scorer uses before its built-in default.

This is intentionally conservative: USDA report schemas vary by report, so the
report slug and the per-mile field name are configurable, and ANY failure
(no key, bad slug, unparseable rows) leaves the built-in reference untouched.
Verify the field mapping against your chosen report once you have a key.
"""
from datetime import datetime
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config, models

_BASE = "https://marsapi.ams.usda.gov/services/v1.2/reports"
_TIMEOUT = 20.0


def configured() -> bool:
    return bool(config.USDA_API_KEY and config.USDA_TRUCK_REPORT_SLUG)


def _to_cents_per_mile(raw) -> int | None:
    """Accept a dollars/mile value (e.g. '2.45' or 2.45) -> cents."""
    try:
        v = float(str(raw).replace("$", "").replace(",", "").strip())
    except (ValueError, TypeError):
        return None
    if v <= 0:
        return None
    # Heuristic: values >20 are almost certainly already in cents.
    return int(round(v if v > 20 else v * 100))


def fetch_rows() -> list[dict] | None:
    if not configured():
        return None
    try:
        r = httpx.get(
            f"{_BASE}/{config.USDA_TRUCK_REPORT_SLUG}",
            auth=(config.USDA_API_KEY, ""),  # MARS: key as basic-auth username
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        # MARS returns either a list or {"results": [...]}.
        rows = data.get("results") if isinstance(data, dict) else data
        return rows if isinstance(rows, list) else None
    except (httpx.HTTPError, ValueError):
        return None


def refresh(db: Session) -> int:
    """Store a national reference rate from the report's average. Returns rows used."""
    rows = fetch_rows()
    if not rows:
        return 0

    rpms = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        cents = _to_cents_per_mile(row.get(config.USDA_RPM_FIELD))
        if cents is not None:
            rpms.append(cents)
    if not rpms:
        return 0

    avg = int(round(sum(rpms) / len(rpms)))
    period = datetime.utcnow().strftime("%Y-%m-%d")
    existing = db.execute(
        select(models.ReferenceRate).where(
            models.ReferenceRate.equipment == config.USDA_EQUIPMENT,
            models.ReferenceRate.region == "US",
            models.ReferenceRate.source == "usda_ams",
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(models.ReferenceRate(
            equipment=config.USDA_EQUIPMENT, region="US", rpm_cents=avg,
            source="usda_ams", period=period,
        ))
    else:
        existing.rpm_cents = avg
        existing.period = period
        existing.fetched_at = datetime.utcnow()
    db.commit()
    return len(rpms)
