"""Scrape MyLittleSalesman search results for semi trucks and dry van trailers."""
import re
from sqlalchemy.orm import Session
from ._base import scrape_search_pages

SEARCH_PAGES = [
    ("https://www.mylittlesalesman.com/trucks/semi-trucks", "truck_sleeper"),
    ("https://www.mylittlesalesman.com/trailers/dry-van-trailers", "trailer_dryvan_53"),
]

_RE = re.compile(r'mylittlesalesman\.com/item/\d+', re.I)


def _is_listing(url: str) -> bool:
    return bool(_RE.search(url))


def run(db: Session) -> dict:
    return scrape_search_pages("mylittlesalesman", SEARCH_PAGES, _is_listing, db)
