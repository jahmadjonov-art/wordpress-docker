"""Scrape CommercialTruckTrader search results for semi trucks and trailers."""
import re
from sqlalchemy.orm import Session
from ._base import scrape_search_pages

SEARCH_PAGES = [
    ("https://www.commercialtrucktrader.com/trucks-for-sale/", "truck_sleeper"),
    ("https://www.commercialtrucktrader.com/trailers-for-sale/", "trailer_dryvan_53"),
]

_RE = re.compile(r'commercialtrucktrader\.com/listing/[^/]+/\d+', re.I)


def _is_listing(url: str) -> bool:
    return bool(_RE.search(url))


def run(db: Session) -> dict:
    return scrape_search_pages("commercial_truck_trader", SEARCH_PAGES, _is_listing, db)
