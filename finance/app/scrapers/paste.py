"""Paste-URL importer: fetch a listing page, try JSON-LD Product schema first,
fall back to BeautifulSoup selectors, fall back to dumping cleaned text for
manual review.

Used for TruckPaper, CommercialTruckTrader, MyLittleSalesman, FB Marketplace
(FB usually fails — the driver then copy-pastes the description into the
manual form)."""
import json
import re
from datetime import datetime
import httpx
from bs4 import BeautifulSoup

from ..scoring.parser import autofill_from_text

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}

TIMEOUT = httpx.Timeout(15.0)


def _source_from_url(url: str) -> str:
    u = url.lower()
    if "truckpaper.com" in u:
        return "truckpaper"
    if "commercialtrucktrader.com" in u:
        return "commercial_truck_trader"
    if "mylittlesalesman.com" in u:
        return "mylittlesalesman"
    if "facebook.com" in u or "fb.com" in u:
        return "fb_marketplace"
    if "craigslist.org" in u:
        return "craigslist"
    if "ebay.com" in u:
        return "ebay"
    return "manual"


def _parse_jsonld(soup: BeautifulSoup) -> dict | None:
    """Many sites emit Product / Vehicle schema.org JSON-LD."""
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            raw = tag.string or tag.get_text() or ""
            data = json.loads(raw)
        except Exception:
            continue
        candidates = data if isinstance(data, list) else [data]
        for d in candidates:
            if not isinstance(d, dict):
                continue
            t = d.get("@type")
            if isinstance(t, list):
                ts = [x.lower() for x in t if isinstance(x, str)]
            else:
                ts = [t.lower()] if isinstance(t, str) else []
            if any(x in ts for x in ("product", "vehicle", "car", "truck")):
                return d
    return None


def _clean_text(soup: BeautifulSoup) -> str:
    for s in soup(["script", "style", "nav", "header", "footer"]):
        s.decompose()
    text = soup.get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text)[:20000]


def fetch_and_parse(url: str) -> dict:
    """Return a dict of listing fields ready to instantiate a Listing.
    Raises httpx.HTTPError on network failure.
    """
    with httpx.Client(follow_redirects=True, timeout=TIMEOUT, headers=DEFAULT_HEADERS) as client:
        resp = client.get(url)
        resp.raise_for_status()
        html = resp.text

    soup = BeautifulSoup(html, "html.parser")
    source = _source_from_url(url)
    title = (soup.title.string or "").strip() if soup.title else ""
    description = ""
    price_cents = None
    photos: list[str] = []

    # JSON-LD first
    jl = _parse_jsonld(soup)
    if jl:
        title = jl.get("name") or title
        description = jl.get("description") or ""
        offers = jl.get("offers") or {}
        if isinstance(offers, list) and offers:
            offers = offers[0]
        if isinstance(offers, dict):
            p = offers.get("price")
            try:
                if p is not None:
                    price_cents = int(round(float(p) * 100))
            except (ValueError, TypeError):
                price_cents = None
        imgs = jl.get("image") or []
        if isinstance(imgs, str):
            photos = [imgs]
        elif isinstance(imgs, list):
            photos = [i for i in imgs if isinstance(i, str)]

    # fallback to <meta og:> + page text
    if not title:
        og = soup.find("meta", property="og:title")
        if og and og.get("content"):
            title = og["content"]
    if not description:
        og = soup.find("meta", property="og:description")
        if og and og.get("content"):
            description = og["content"]
    if not photos:
        og = soup.find("meta", property="og:image")
        if og and og.get("content"):
            photos = [og["content"]]

    full_text = f"{title}\n{description}\n{_clean_text(soup)}"
    autofill = autofill_from_text(title, description + "\n" + _clean_text(soup))
    if price_cents is None:
        price_cents = autofill.get("asking_price_cents")

    return {
        "source": source,
        "source_url": url,
        "title": title or url,
        "asking_price_cents": price_cents,
        "description": description[:5000] if description else None,
        "photos_json": json.dumps(photos) if photos else None,
        "year": autofill.get("year"),
        "make": autofill.get("make"),
        "model": autofill.get("model"),
        "engine": autofill.get("engine"),
        "mileage": autofill.get("mileage"),
        "vin": autofill.get("vin"),
        "category": autofill.get("category"),
        "trailer_length_ft": autofill.get("trailer_length_ft"),
        "trailer_walls": autofill.get("trailer_walls"),
        "trailer_door": autofill.get("trailer_door"),
        "trailer_suspension": autofill.get("trailer_suspension"),
        "fetch_method": "paste",
        "raw_html_len": len(html),
    }
