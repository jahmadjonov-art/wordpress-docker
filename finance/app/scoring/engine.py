"""Top-level entry: score a listing and persist a ListingScore row."""
import json
from datetime import datetime
from sqlalchemy.orm import Session

from .. import models
from .truck import score_truck
from .trailer import score_trailer


def score_and_save(db: Session, listing: models.Listing) -> models.ListingScore:
    if listing.category in ("truck_sleeper", "truck_daycab"):
        score, confidence, comp_count, median_cents, breakdown = score_truck(db, listing)
    elif listing.category in ("trailer_dryvan_53", "trailer_reefer"):
        score, confidence, comp_count, median_cents, breakdown = score_trailer(db, listing)
    else:
        score, confidence, comp_count, median_cents, breakdown = 50, 0.0, 0, None, {"items": [("unknown category", 0)]}

    row = models.ListingScore(
        listing_id=listing.id,
        scored_at=datetime.utcnow(),
        score=int(score),
        confidence=float(confidence),
        comp_count=int(comp_count),
        median_comp_cents=median_cents,
        breakdown_json=json.dumps(breakdown["items"]),
    )
    db.add(row)
    db.commit()
    return row


def rescore_all(db: Session) -> int:
    count = 0
    for listing in db.query(models.Listing).filter(models.Listing.status == "active").all():
        score_and_save(db, listing)
        count += 1
    return count
