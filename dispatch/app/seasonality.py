"""Produce-season awareness.

Reefer demand and rates swing with the U.S. produce harvest calendar (roughly
May–July nationally, with regional spikes). We don't have a live seasonal feed,
so we encode a coarse, transparent calendar that nudges the cold-start reference
rate and surfaces a context flag on the load. Source basis: USDA NASS crop
calendars + DAT/industry reefer-season norms.
"""
from datetime import date

# Months where reefer demand is broadly elevated nationally (1=Jan).
_NATIONAL_PEAK_MONTHS = {5, 6, 7}        # produce season core
_NATIONAL_SHOULDER_MONTHS = {4, 8, 9}    # ramp / tail

# Region-specific produce heat by month (origin region -> set of peak months).
# Regions match scoring.modifiers.region_for codes.
_REGION_PEAKS = {
    "SE": {1, 2, 3, 4, 5, 6},     # FL/GA winter + spring produce
    "SC": {3, 4, 5, 6},           # TX
    "PAC": {6, 7, 8, 9, 10},      # CA central valley + PNW apples
    "W": {7, 8, 9},
}


def reefer_factor(equipment: str, when: date | None, origin_region: str | None) -> tuple[float, str | None]:
    """Return (multiplier, note) to scale a reference reefer rate by season.

    1.0 means neutral. Only applies to reefer. The note is a short human flag,
    or None when nothing notable.
    """
    if equipment != "reefer" or when is None:
        return (1.0, None)

    m = when.month
    region_hot = origin_region in _REGION_PEAKS and m in _REGION_PEAKS[origin_region]

    if m in _NATIONAL_PEAK_MONTHS or region_hot:
        return (1.30, "Produce season — reefer demand elevated")
    if m in _NATIONAL_SHOULDER_MONTHS:
        return (1.12, "Produce shoulder season — reefer firming")
    return (0.95, "Produce off-season — reefer softer")
