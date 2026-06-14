"""Cold-start reference rates.

The lane benchmark is built from the user's own logged loads, which is empty on
day one. Until a lane has enough comps, we fall back to a transparent national
baseline rate-per-mile by equipment, seasonally adjusted for reefer. These are
ballpark 2025–2026 U.S. spot averages (van/reefer/flatbed) meant to be edited;
swap in live USDA AMS / DAT-index values when available.
"""
from datetime import date

from .. import seasonality
from .modifiers import region_for

# National baseline all-in spot rate-per-mile, in cents. Editable.
BASELINE_RPM_CENTS = {
    "van": 195,
    "reefer": 230,
    "flatbed": 250,
}

# Minimum lane comps before we trust the user's own benchmark over the reference.
MIN_COMPS_FOR_LANE = 5


def reference_rpm_cents(equipment: str, when: date | None, origin_state: str | None) -> tuple[int, str | None]:
    """Return (reference rate/mi in cents, optional season note)."""
    base = BASELINE_RPM_CENTS.get(equipment, BASELINE_RPM_CENTS["van"])
    factor, note = seasonality.reefer_factor(equipment, when, region_for(origin_state))
    return (int(round(base * factor)), note)
