"""EIA diesel price lookup, cached in the FuelPrice table.

Uses the EIA v2 open-data API series for U.S. No.2 diesel retail price
(dollars/gallon, weekly). Falls back to DEFAULT_DIESEL_CPG when no key is
configured or the request fails.
"""
from datetime import datetime
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config, models

# U.S. retail diesel, weekly (EIA series EMD_EPD2D_PTE_NUS_DPG)
_EIA_URL = "https://api.eia.gov/v2/petroleum/pri/gnd/data/"
_TIMEOUT = 15.0


def fetch_diesel_cpg() -> tuple[int, str] | None:
    """Return (cents_per_gallon, period) from EIA, or None on failure/no key."""
    if not config.EIA_API_KEY:
        return None
    try:
        r = httpx.get(
            _EIA_URL,
            params={
                "api_key": config.EIA_API_KEY,
                "frequency": "weekly",
                "data[0]": "value",
                "facets[series][]": "EMD_EPD2D_PTE_NUS_DPG",
                "sort[0][column]": "period",
                "sort[0][direction]": "desc",
                "length": 1,
            },
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        rows = r.json()["response"]["data"]
        if not rows:
            return None
        dollars = float(rows[0]["value"])
        return (int(round(dollars * 100)), str(rows[0]["period"]))
    except (httpx.HTTPError, KeyError, ValueError, IndexError):
        return None


def refresh(db: Session) -> int:
    """Fetch and store the latest diesel price. Returns cents/gallon used."""
    result = fetch_diesel_cpg()
    if result is None:
        return current_cpg(db)
    cpg, period = result
    row = db.execute(select(models.FuelPrice).where(models.FuelPrice.region == "US")).scalar_one_or_none()
    if row is None:
        row = models.FuelPrice(region="US", diesel_cents_per_gal=cpg, period=period)
        db.add(row)
    else:
        row.diesel_cents_per_gal = cpg
        row.period = period
        row.fetched_at = datetime.utcnow()
    db.commit()
    return cpg


def current_cpg(db: Session) -> int:
    """Most recent cached diesel price, or the configured default."""
    row = db.execute(select(models.FuelPrice).where(models.FuelPrice.region == "US")).scalar_one_or_none()
    if row is not None:
        return row.diesel_cents_per_gal
    return config.DEFAULT_DIESEL_CPG
