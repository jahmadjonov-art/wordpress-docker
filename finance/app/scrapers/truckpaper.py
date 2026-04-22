"""Scrape TruckPaper search results for semi trucks and 53ft dry van trailers."""
import re
from sqlalchemy.orm import Session
from ._base import scrape_search_pages

SEARCH_PAGES = [
    ("https://www.truckpaper.com/listings/trucks/for-sale/category/semi-trucks", "truck_sleeper"),
    ("https://www.truckpaper.com/listings/trailers/for-sale/category/dry-van-trailers-53-ft", "trailer_dryvan_53"),
]

_RE = re.compile(r'truckpaper\.com/listings/[^/]+/for-sale/list/\d+', re.I)


def _is_listing(url: str) -> bool:
    return bool(_RE.search(url))


def run(db: Session) -> dict:
    return scrape_search_pages("truckpaper", SEARCH_PAGES, _is_listing, db)
