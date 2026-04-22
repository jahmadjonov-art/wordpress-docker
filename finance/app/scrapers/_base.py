"""Shared logic for HTML search-page scrapers."""
import json
import re
import time
import random
from datetime import datetime
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..scrapers.paste import fetch_and_parse
from ..scoring.engine import score_and_save

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

_LISTING_FIELDS = {c.key for c in models.Listing.__table__.columns}


def _listing_urls_from_html(html: str, base_url: str, is_listing: callable) -> set[str]:
    soup = BeautifulSoup(html, "html.parser")
    urls = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].split("?")[0].rstrip("/")
        if not href.startswith("http"):
            href = urljoin(base_url, href)
        if is_listing(href):
            urls.add(href)
    return urls


def scrape_search_pages(
    source: str,
    search_pages: list[tuple[str, str]],
    is_listing: callable,
    db: Session,
    pages: int = 2,
) -> dict:
    run_row = models.ScrapeRun(source=source, started_at=datetime.utcnow())
    db.add(run_row)
    db.commit()
    db.refresh(run_row)

    new = updated = 0
    errors: list[str] = []

    with httpx.Client(follow_redirects=True, timeout=25.0, headers=HEADERS) as client:
        for search_url, default_category in search_pages:
            for page in range(1, pages + 1):
                paged_url = search_url if page == 1 else f"{search_url}?page={page}"
                try:
                    resp = client.get(paged_url)
                    if resp.status_code != 200:
                        errors.append(f"{paged_url} -> HTTP {resp.status_code}")
                        continue
                    listing_urls = _listing_urls_from_html(resp.text, search_url, is_listing)
                except Exception as e:
                    errors.append(f"{paged_url}: {type(e).__name__}: {e}")
                    continue

                for url in listing_urls:
                    existing = db.execute(
                        select(models.Listing).where(models.Listing.source_url == url)
                    ).scalar_one_or_none()
                    if existing:
                        existing.last_seen = datetime.utcnow()
                        db.commit()
                        updated += 1
                        continue
                    try:
                        data = fetch_and_parse(url)
                        if data.get("category") == "other":
                            data["category"] = default_category
                        data["source"] = source
                        data["fetch_method"] = "scrape"
                        safe = {k: v for k, v in data.items() if k in _LISTING_FIELDS}
                        listing = models.Listing(**safe)
                        db.add(listing)
                        db.commit()
                        db.refresh(listing)
                        score_and_save(db, listing)
                        new += 1
                    except Exception as e:
                        errors.append(f"{url}: {type(e).__name__}: {e}")
                    time.sleep(random.uniform(1.5, 3.0))

                time.sleep(random.uniform(2.0, 4.0))

    run_row.finished_at = datetime.utcnow()
    run_row.listings_new = new
    run_row.listings_updated = updated
    run_row.errors_json = json.dumps(errors[:50]) if errors else None
    run_row.status = "ok" if not errors else ("partial" if new or updated else "fail")
    db.commit()
    return {"new": new, "updated": updated, "errors": len(errors)}
