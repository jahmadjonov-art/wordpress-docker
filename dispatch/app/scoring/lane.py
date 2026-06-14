"""Build lane rate cohorts from observed loads and persist percentiles.

Directly mirrors finance/app/scoring/market.py: a lane cohort is keyed by
(origin region -> dest region -> equipment); we collect rate-per-mile across
loads in the cohort and store median / p25 / p75. Comps widen progressively
when an exact lane has too few samples.
"""
import statistics
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from .modifiers import region_for


def lane_key(load: models.Load) -> str:
    return f"{load.equipment}|{region_for(load.origin_state)}|{region_for(load.dest_state)}"


def _scored_loads(db: Session) -> list[models.Load]:
    return db.execute(
        select(models.Load).where(
            models.Load.status == "active",
            models.Load.rate_per_mile_cents.is_not(None),
        )
    ).scalars().all()


def find_comps(db: Session, load: models.Load) -> list[int]:
    """Return rate-per-mile (cents) of comparable loads, widening if too few."""
    key = lane_key(load)
    others = [
        l for l in _scored_loads(db)
        if l.id != load.id and l.rate_per_mile_cents
    ]

    same_lane = [l.rate_per_mile_cents for l in others if lane_key(l) == key]
    if len(same_lane) >= 5:
        return same_lane

    # widen: same equipment + same origin region (any destination)
    o_region = region_for(load.origin_state)
    widened = [
        l.rate_per_mile_cents for l in others
        if l.equipment == load.equipment and region_for(l.origin_state) == o_region
    ]
    if len(widened) >= 5:
        return widened

    # last resort: same equipment anywhere
    same_equip = [l.rate_per_mile_cents for l in others if l.equipment == load.equipment]
    return same_equip


def compute_lane_stats(db: Session) -> int:
    """Recompute lane_stats for every distinct cohort. Returns cohort count."""
    loads = _scored_loads(db)

    by_key: dict[str, list[models.Load]] = {}
    for l in loads:
        by_key.setdefault(lane_key(l), []).append(l)

    db.query(models.LaneStat).delete()
    now = datetime.utcnow()
    for key, group in by_key.items():
        rpms = sorted(l.rate_per_mile_cents for l in group)
        if not rpms:
            continue
        equipment, o_region, d_region = key.split("|")
        db.add(
            models.LaneStat(
                lane_key=key,
                equipment=equipment,
                origin_region=o_region,
                dest_region=d_region,
                sample_count=len(rpms),
                median_rpm_cents=int(statistics.median(rpms)),
                p25_cents=rpms[len(rpms) // 4] if len(rpms) >= 4 else None,
                p75_cents=rpms[(3 * len(rpms)) // 4] if len(rpms) >= 4 else None,
                computed_at=now,
            )
        )
    db.commit()
    return len(by_key)
