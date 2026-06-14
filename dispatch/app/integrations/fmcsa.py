"""FMCSA QCMobile broker/carrier lookup by MC number, cached in Broker table.

Free WebKey required (FMCSA_WEBKEY). Without it, lookups return None and the
UI shows a "configure key" notice.
"""
import json
from datetime import datetime
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config, models

_BASE = "https://mobile.fmcsa.dot.gov/qc/services/carriers"
_TIMEOUT = 15.0


def configured() -> bool:
    return bool(config.FMCSA_WEBKEY)


def _clean_mc(mc: str) -> str:
    return "".join(ch for ch in (mc or "") if ch.isdigit())


def lookup(db: Session, mc_number: str, max_age_hours: int = 24) -> models.Broker | None:
    """Return a Broker record for the MC number, fetching from FMCSA if stale."""
    mc = _clean_mc(mc_number)
    if not mc:
        return None

    existing = db.execute(
        select(models.Broker).where(models.Broker.mc_number == mc)
    ).scalar_one_or_none()
    if existing is not None:
        age = (datetime.utcnow() - existing.last_checked).total_seconds() / 3600
        if age < max_age_hours:
            return existing

    if not configured():
        return existing  # may be a stale cached row, or None

    data = _fetch(mc)
    if data is None:
        return existing

    content = data.get("content")
    if isinstance(content, list):
        content = content[0] if content else {}
    carrier = (content or {}).get("carrier") or {}
    if not carrier:
        return existing

    fields = dict(
        legal_name=carrier.get("legalName"),
        dba_name=carrier.get("dbaName"),
        allowed_to_operate=carrier.get("allowedToOperate"),
        safety_rating=carrier.get("safetyRating"),
        authority_status="active" if carrier.get("allowedToOperate") == "Y" else "inactive",
        raw_json=json.dumps(carrier)[:8000],
        last_checked=datetime.utcnow(),
    )
    if existing is None:
        existing = models.Broker(mc_number=mc, **fields)
        db.add(existing)
    else:
        for k, v in fields.items():
            setattr(existing, k, v)
    db.commit()
    return existing


def _fetch(mc: str) -> dict | None:
    try:
        r = httpx.get(
            f"{_BASE}/docket-number/{mc}",
            params={"webKey": config.FMCSA_WEBKEY},
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        return r.json()
    except (httpx.HTTPError, ValueError):
        return None
