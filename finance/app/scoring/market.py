"""Build market comp cohorts from the `listings` table and persist medians."""
import statistics
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from .modifiers import mileage_band


def _truck_cohort_key(l: models.Listing) -> str | None:
    if not l.year or not l.make:
        return None
    band = mileage_band(l.mileage) or "unknown"
    yspan = (l.year // 2) * 2  # 2-year buckets
    return f"truck|{l.make}|{l.model or ''}|{yspan}|{band}"


def _trailer_cohort_key(l: models.Listing) -> str | None:
    if not l.year:
        return None
    yspan = (l.year // 3) * 3
    return f"trailer|{l.trailer_length_ft or 53}|{l.trailer_suspension or 'any'}|{yspan}"


def cohort_key(l: models.Listing) -> str | None:
    if l.category in ("truck_sleeper", "truck_daycab"):
        return _truck_cohort_key(l)
    if l.category in ("trailer_dryvan_53", "trailer_reefer"):
        return _trailer_cohort_key(l)
    return None


def find_comps(db: Session, listing: models.Listing) -> list[models.Listing]:
    """Find comparable active listings. Widens if too few."""
    key = cohort_key(listing)
    if key is None:
        return []

    all_same_cat = db.execute(
        select(models.Listing).where(
            models.Listing.category == listing.category,
            models.Listing.status == "active",
            models.Listing.asking_price_cents.is_not(None),
            models.Listing.id != listing.id,
        )
    ).scalars().all()

    same_cohort = [l for l in all_same_cat if cohort_key(l) == key]
    if len(same_cohort) >= 5:
        return same_cohort

    # widen: same category + same make for trucks / same length for trailers + year ±4
    widened = []
    if listing.category.startswith("truck"):
        for l in all_same_cat:
            if l.make == listing.make and l.year and listing.year and abs(l.year - listing.year) <= 4:
                widened.append(l)
    else:
        for l in all_same_cat:
            if (l.trailer_length_ft or 53) == (listing.trailer_length_ft or 53) \
               and l.year and listing.year and abs(l.year - listing.year) <= 5:
                widened.append(l)
    if len(widened) >= 5:
        return widened

    # last resort: whole category
    return all_same_cat


def compute_cohort_stats(db: Session) -> int:
    """Recompute market_stats for every distinct cohort. Returns number of cohorts stored."""
    listings = db.execute(
        select(models.Listing).where(
            models.Listing.status == "active",
            models.Listing.asking_price_cents.is_not(None),
        )
    ).scalars().all()

    by_key: dict[str, list[models.Listing]] = {}
    for l in listings:
        k = cohort_key(l)
        if k:
            by_key.setdefault(k, []).append(l)

    # wipe & rebuild
    db.query(models.MarketStat).delete()
    now = datetime.utcnow()
    for k, group in by_key.items():
        prices = sorted(l.asking_price_cents for l in group)
        if not prices:
            continue
        first = group[0]
        db.add(
            models.MarketStat(
                cohort_key=k,
                category=first.category,
                make=first.make,
                model=first.model,
                year_min=min((l.year for l in group if l.year), default=None),
                year_max=max((l.year for l in group if l.year), default=None),
                mileage_band=mileage_band(first.mileage),
                sample_count=len(prices),
                median_cents=int(statistics.median(prices)),
                p25_cents=prices[len(prices) // 4] if len(prices) >= 4 else None,
                p75_cents=prices[(3 * len(prices)) // 4] if len(prices) >= 4 else None,
                computed_at=now,
            )
        )
    db.commit()
    return len(by_key)
