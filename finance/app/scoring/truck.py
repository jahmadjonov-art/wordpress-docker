"""Score a truck listing 0-100."""
import json
import re
import statistics
from sqlalchemy.orm import Session

from .. import models, config
from .modifiers import (
    TRUCK_MODEL_MODS,
    EMISSIONS_ERAS,
    TRANSMISSION_MODS,
    TRUCK_MILEAGE_MODS,
    TRUCK_CONDITION_KEYWORDS,
    TRUCK_KEYWORD_CAPS,
    COMPLETENESS_PENALTIES,
    mileage_band,
)
from .market import find_comps


def _apply_keywords(text: str, table, caps) -> tuple[int, list[tuple[str, int]]]:
    """Apply regex keyword rules; cap each group's net delta."""
    bucket: dict[str, int] = {}
    hits: list[tuple[str, int]] = []
    for pattern, mod, label, group in table:
        if re.search(pattern, text, flags=re.IGNORECASE):
            bucket[group] = bucket.get(group, 0) + mod
            hits.append((label, mod))
    delta = 0
    for group, amt in bucket.items():
        cap = caps.get(group, 999)
        if cap >= 0:
            amt = min(amt, cap)
        else:
            amt = max(amt, cap)
        delta += amt
    return delta, hits


def score_truck(db: Session, listing: models.Listing) -> tuple[int, float, int, int | None, dict]:
    breakdown: list[tuple[str, int]] = []
    hard_cap: int | None = None  # "this is a trap" ceilings
    text = f"{listing.title or ''}\n{listing.description or ''}"

    # --- base: price vs median comps ---
    comps = find_comps(db, listing)
    comp_prices = [c.asking_price_cents for c in comps if c.asking_price_cents]
    if comp_prices and listing.asking_price_cents:
        median = statistics.median(comp_prices)
        ratio = (median - listing.asking_price_cents) / median
        base = 50 + max(-50, min(50, int(ratio * 100)))
        breakdown.append((f"Price vs median of {len(comp_prices)} comps ({median/100:.0f})", base - 50))
        confidence = min(1.0, len(comp_prices) / 15.0)
        median_cents = int(median)
        comp_count = len(comp_prices)
    else:
        base = 50
        breakdown.append(("No comps available — neutral base", 0))
        confidence = 0.1
        median_cents = None
        comp_count = 0

    score = base

    # --- model / engine / era ---
    for make, model_sub, engine_sub, y_min, y_max, mod, label in TRUCK_MODEL_MODS:
        if (listing.make or "").lower() != make:
            continue
        if model_sub and model_sub not in (listing.model or "").lower():
            continue
        if engine_sub and engine_sub not in (listing.engine or "").lower():
            continue
        if listing.year and not (y_min <= listing.year <= y_max):
            continue
        score += mod
        breakdown.append((label, mod))
        # hard caps for "avoid" models
        if "avoid" in label.lower() or "maxxforce" in label.lower():
            hard_cap = 35
        break  # take the most specific match

    if listing.year:
        for y_min, y_max, mod_non_ca, mod_ca, label in EMISSIONS_ERAS:
            if y_min <= listing.year <= y_max:
                mod = mod_ca if config.CA_OPERATION else mod_non_ca
                score += mod
                breakdown.append((label, mod))
                break

    tx = (listing.transmission or "").lower()
    tx_key = None
    if "allison" in tx:
        tx_key = "allison"
    elif any(k in tx for k in ("manual", "10-speed", "13-speed", "18-speed", "eaton")):
        tx_key = "manual"
    elif any(k in tx for k in ("auto", "shift", "ultrashift", "mdrive", "i-shift")):
        tx_key = "automated"
    if tx_key:
        mod, label = TRANSMISSION_MODS[tx_key]
        score += mod
        breakdown.append((label, mod))

    band = mileage_band(listing.mileage)
    if band:
        mod, label = TRUCK_MILEAGE_MODS[band]
        score += mod
        breakdown.append((label, mod))

    # condition keywords (caps "emissions_delete" as hard trap)
    delta, hits = _apply_keywords(text, TRUCK_CONDITION_KEYWORDS, TRUCK_KEYWORD_CAPS)
    for label, mod in hits:
        breakdown.append((label, mod))
    score += delta
    if re.search(r"\b(deleted|dpf\s+delete|egr\s+delete|no\s+dpf)\b", text, re.IGNORECASE):
        hard_cap = min(hard_cap or 35, 35)

    # completeness
    for field, penalty, label in COMPLETENESS_PENALTIES:
        if field == "mileage" and listing.category != "truck_sleeper" and listing.category != "truck_daycab":
            continue
        if field == "engine" and listing.category not in ("truck_sleeper", "truck_daycab"):
            continue
        val = getattr(listing, field, None)
        if not val:
            score += penalty
            breakdown.append((label, penalty))

    # finalize
    if hard_cap is not None:
        score = min(score, hard_cap)
        breakdown.append((f"Hard cap at {hard_cap} (trap)", 0))
    score = max(0, min(100, score))

    return (
        score,
        confidence,
        comp_count,
        median_cents,
        {"items": breakdown},
    )
