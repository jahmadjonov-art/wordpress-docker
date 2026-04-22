"""Score a trailer listing 0-100."""
import re
import statistics
from sqlalchemy.orm import Session

from .. import models
from .modifiers import (
    TRAILER_AGE_MODS,
    TRAILER_WALL_MODS,
    TRAILER_DOOR_MODS,
    TRAILER_SUSPENSION_MODS,
    TRAILER_CONDITION_KEYWORDS,
    TRAILER_KEYWORD_CAPS,
    COMPLETENESS_PENALTIES,
)
from .truck import _apply_keywords
from .market import find_comps


def score_trailer(db: Session, listing: models.Listing) -> tuple[int, float, int, int | None, dict]:
    breakdown: list[tuple[str, int]] = []
    text = f"{listing.title or ''}\n{listing.description or ''}"

    comps = find_comps(db, listing)
    comp_prices = [c.asking_price_cents for c in comps if c.asking_price_cents]
    if comp_prices and listing.asking_price_cents:
        median = statistics.median(comp_prices)
        ratio = (median - listing.asking_price_cents) / median
        # tighter curve for trailers (*75 instead of *100, clamp ±40)
        base = 50 + max(-40, min(40, int(ratio * 75)))
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

    if listing.year:
        for y_min, y_max, mod, label in TRAILER_AGE_MODS:
            if y_min <= listing.year <= y_max:
                score += mod
                breakdown.append((label, mod))
                break

    if listing.trailer_walls and listing.trailer_walls in TRAILER_WALL_MODS:
        mod, label = TRAILER_WALL_MODS[listing.trailer_walls]
        score += mod
        breakdown.append((label, mod))

    if listing.trailer_door and listing.trailer_door in TRAILER_DOOR_MODS:
        mod, label = TRAILER_DOOR_MODS[listing.trailer_door]
        score += mod
        breakdown.append((label, mod))

    if listing.trailer_suspension and listing.trailer_suspension in TRAILER_SUSPENSION_MODS:
        mod, label = TRAILER_SUSPENSION_MODS[listing.trailer_suspension]
        score += mod
        breakdown.append((label, mod))

    delta, hits = _apply_keywords(text, TRAILER_CONDITION_KEYWORDS, TRAILER_KEYWORD_CAPS)
    for label, mod in hits:
        breakdown.append((label, mod))
    score += delta

    # reefer hour penalty parsed from text
    m = re.search(r"(\d{3,5})\s*(hrs|hours)\b", text, re.IGNORECASE)
    if m and listing.category == "trailer_reefer":
        hrs = int(m.group(1))
        mod = -int(hrs * 0.005)
        mod = max(mod, -20)
        score += mod
        breakdown.append((f"Reefer {hrs} hrs", mod))

    for field, penalty, label in COMPLETENESS_PENALTIES:
        if field in ("mileage", "engine"):
            continue  # n/a for trailers
        val = getattr(listing, field, None)
        if not val:
            score += penalty
            breakdown.append((label, penalty))

    score = max(0, min(100, score))
    return (score, confidence, comp_count, median_cents, {"items": breakdown})
