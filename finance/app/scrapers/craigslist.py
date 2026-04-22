"""Poll Craigslist's per-metro commercial-vehicles RSS feeds.

Craigslist allows automated RSS access (it's in their Terms). We request
the /hvo (heavy vehicles) section and their /trb (trailers) section for
each configured metro, dedupe by URL, and insert new listings.

Docs: https://www.craigslist.org/about/help/rss
Feed format: https://<metro>.craigslist.org/search/hvo?format=rss
"""
import json
import time
import httpx
import feedparser
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, config
from ..scoring.parser import autofill_from_text
from ..scoring.engine import score_and_save

USER_AGENT = "Mozilla/5.0 (compatible; TruckDealFinder/0.1; +solo-user)"

SECTIONS = [
    # (subpath, default_category_hint)
    ("hvo", "truck_sleeper"),        # heavy vehicles (semi trucks)
    ("trb", "trailer_dryvan_53"),    # trailers
]


def _feed_url(metro: str, section: str) -> str:
    return f"https://{metro}.craigslist.org/search/{section}?format=rss&purveyor-input=all"


def _parse_entry(entry, metro: str, default_category: str) -> dict:
    title = getattr(entry, "title", "")
    description = getattr(entry, "summary", "") or getattr(entry, "description", "")
    url = getattr(entry, "link", "")
    auto = autofill_from_text(title, description)
    if auto["category"] == "other":
        auto["category"] = default_category
    return {
        "source": "craigslist",
        "source_url": url,
        "title": title,
        "description": description[:4000] if description else None,
        "asking_price_cents": auto.get("asking_price_cents"),
        "year": auto.get("year"),
        "make": auto.get("make"),
        "model": auto.get("model"),
        "engine": auto.get("engine"),
        "mileage": auto.get("mileage"),
        "vin": auto.get("vin"),
        "category": auto.get("category"),
        "trailer_length_ft": auto.get("trailer_length_ft"),
        "trailer_walls": auto.get("trailer_walls"),
        "trailer_door": auto.get("trailer_door"),
        "trailer_suspension": auto.get("trailer_suspension"),
        "location_city": metro,
        "fetch_method": "rss",
    }


def run(db: Session) -> dict:
    run_row = models.ScrapeRun(source="craigslist", started_at=datetime.utcnow())
    db.add(run_row)
    db.commit()
    db.refresh(run_row)

    new = 0
    updated = 0
    errors: list[str] = []

    with httpx.Client(timeout=20.0, headers={"User-Agent": USER_AGENT}) as client:
        for metro in config.CRAIGSLIST_METROS:
            for section, default_category in SECTIONS:
                url = _feed_url(metro, section)
                try:
                    resp = client.get(url)
                    if resp.status_code != 200:
                        errors.append(f"{url} -> HTTP {resp.status_code}")
                        continue
                    feed = feedparser.parse(resp.content)
                    for entry in feed.entries:
                        data = _parse_entry(entry, metro, default_category)
                        if not data["source_url"]:
                            continue
                        existing = db.execute(
                            select(models.Listing).where(models.Listing.source_url == data["source_url"])
                        ).scalar_one_or_none()
                        if existing:
                            existing.last_seen = datetime.utcnow()
                            db.commit()
                            updated += 1
                            continue
                        listing = models.Listing(**data)
                        db.add(listing)
                        db.commit()
                        db.refresh(listing)
                        try:
                            score_and_save(db, listing)
                        except Exception as e:
                            errors.append(f"score {listing.source_url}: {e}")
                        new += 1
                    time.sleep(1.0)  # polite between feeds
                except Exception as e:
                    errors.append(f"{url}: {type(e).__name__}: {e}")

    run_row.finished_at = datetime.utcnow()
    run_row.listings_new = new
    run_row.listings_updated = updated
    run_row.errors_json = json.dumps(errors[:50]) if errors else None
    run_row.status = "ok" if not errors else ("partial" if new or updated else "fail")
    db.commit()
    return {"new": new, "updated": updated, "errors": len(errors)}
