"""Backhaul lane-pairing.

For a given load, find the user's *other* logged loads that pick up near where
this one drops — i.e. freight that gets the truck loaded again instead of
running empty home. Scores the round trip, not just the headhaul. Pure compute
on the user's own history + stored coordinates; no external calls.
"""
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..integrations.routing import haversine_miles, ROAD_FACTOR


@dataclass
class Backhaul:
    load: models.Load
    connect_miles: float        # deadhead from this load's drop to the candidate's pickup
    candidate_rpm_cents: int | None


@dataclass
class RoundTrip:
    total_miles: float
    total_rate_cents: int
    rpm_cents: int              # combined rate over all miles (loaded + every empty)


def find_backhauls(db: Session, load: models.Load, radius_miles: float = 150.0,
                   limit: int = 5, same_equipment: bool = True) -> list[Backhaul]:
    if load.dest_lat is None or load.dest_lng is None:
        return []

    q = select(models.Load).where(
        models.Load.status == "active",
        models.Load.id != load.id,
        models.Load.origin_lat.is_not(None),
    )
    if same_equipment:
        q = q.where(models.Load.equipment == load.equipment)
    candidates = db.execute(q).scalars().all()

    out: list[Backhaul] = []
    for c in candidates:
        connect = haversine_miles((load.dest_lat, load.dest_lng),
                                  (c.origin_lat, c.origin_lng)) * ROAD_FACTOR
        if connect <= radius_miles:
            out.append(Backhaul(load=c, connect_miles=round(connect, 1),
                                candidate_rpm_cents=c.rate_per_mile_cents))
    # closest connect first (least empty), then best paying
    out.sort(key=lambda b: (b.connect_miles, -(b.candidate_rpm_cents or 0)))
    return out[:limit]


def round_trip(load: models.Load, back: Backhaul) -> RoundTrip | None:
    """Combine the headhaul and a chosen backhaul into round-trip economics."""
    c = back.load
    if not (load.rate_total_cents and c.rate_total_cents and load.loaded_miles and c.loaded_miles):
        return None
    total_miles = (
        (load.loaded_miles or 0) + (load.deadhead_miles or 0)
        + back.connect_miles
        + (c.loaded_miles or 0) + (c.deadhead_miles or 0)
    )
    total_rate = load.rate_total_cents + c.rate_total_cents
    rpm = int(round(total_rate / total_miles)) if total_miles else 0
    return RoundTrip(total_miles=round(total_miles, 1), total_rate_cents=total_rate, rpm_cents=rpm)
