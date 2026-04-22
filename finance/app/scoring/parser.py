"""Regex extractors to pull structured fields from free-form listing text."""
import re

MAKES = {
    "freightliner": ["freightliner", "fl "],
    "kenworth":     ["kenworth", "kw "],
    "peterbilt":    ["peterbilt", "pete "],
    "volvo":        ["volvo"],
    "international":["international", "intl ", "navistar"],
    "mack":         ["mack"],
    "western star": ["western star", "westernstar"],
}

MODEL_KEYWORDS = [
    "cascadia", "columbia", "coronado",
    "t680", "t880", "t800", "w900", "t660",
    "579", "389", "579ultra", "567", "386",
    "vnl", "vnr", "vhd",
    "lt", "rh", "prostar", "lonestar", "9200",
    "anthem", "pinnacle", "granite",
    "5700", "4900",
]

ENGINES = {
    "dd15": ["dd15", "detroit 15", "dd-15"],
    "dd13": ["dd13", "detroit 13", "dd-13"],
    "dd16": ["dd16", "detroit 16"],
    "x15":  ["x15", "isx15", "cummins x15", "cummins 15"],
    "isx":  ["isx", "cummins isx"],
    "mx13": ["mx13", "mx-13", "paccar mx"],
    "d13":  ["d13", "volvo d13"],
    "d11":  ["d11"],
    "mp8":  ["mp8", "mp-8"],
    "a26":  ["a26", "international a26"],
    "maxxforce": ["maxxforce", "max force", "maxforce"],
    "n14":  ["n14"],
    "series 60": ["series 60", "s60", "detroit 60"],
}

TRAILER_WALL_KEYWORDS = {
    "composite": ["duraplate", "plate wall", "composite", "everest", "4000d-x", "4000dx"],
    "aluminum_sheet_post": ["sheet and post", "sheet-and-post", "s&p"],
    "aluminum_smooth": ["smooth skin", "smoothside", "smooth side"],
}

TRAILER_DOOR_KEYWORDS = {
    "swing": ["swing door", "swing doors", "barn door"],
    "rollup": ["roll up", "roll-up", "rollup", "overhead door"],
}

TRAILER_SUSPENSION_KEYWORDS = {
    "air": ["air ride", "air-ride", "airride"],
    "spring": ["spring ride", "spring-ride", "spring susp"],
}

YEAR_RE = re.compile(r"\b(19[89]\d|20[0-3]\d)\b")
MILES_RE = re.compile(
    r"\b([0-9][0-9,\.]{2,})\s*(k|thousand|mi|mile|miles)?\b",
    re.IGNORECASE,
)
MILES_K_RE = re.compile(r"\b(\d{2,4})\s*k\s*(mi|miles)?\b", re.IGNORECASE)
PRICE_RE = re.compile(r"\$\s*([0-9][0-9,]{2,}(?:\.[0-9]{2})?)")
VIN_RE = re.compile(r"\b([A-HJ-NPR-Z0-9]{17})\b")
TRAILER_LEN_RE = re.compile(r"\b(48|53)\s*['ft\. ]", re.IGNORECASE)


def _first_year(text: str) -> int | None:
    m = YEAR_RE.search(text)
    return int(m.group(1)) if m else None


def extract_make(text: str) -> str | None:
    t = text.lower()
    for make, keys in MAKES.items():
        for k in keys:
            if k in t:
                return make
    return None


def extract_model(text: str) -> str | None:
    t = text.lower()
    for m in MODEL_KEYWORDS:
        if re.search(rf"\b{re.escape(m)}\b", t):
            return m
    return None


def extract_engine(text: str) -> str | None:
    t = text.lower()
    for engine, keys in ENGINES.items():
        for k in keys:
            if k in t:
                return engine
    return None


def extract_mileage(text: str) -> int | None:
    t = text.replace(",", "").lower()
    m = MILES_K_RE.search(t)
    if m:
        return int(m.group(1)) * 1000
    # try "400000 miles" style
    m = re.search(r"\b(\d{5,7})\s*(mi|mile|miles)\b", t)
    if m:
        return int(m.group(1))
    # heuristic: big number followed by "mile"
    m = re.search(r"\b(\d{5,7})\b.*?\b(mile|mi)\b", t)
    if m:
        return int(m.group(1))
    return None


def extract_price(text: str) -> int | None:
    """Returns cents."""
    m = PRICE_RE.search(text)
    if not m:
        return None
    raw = m.group(1).replace(",", "")
    try:
        return int(round(float(raw) * 100))
    except ValueError:
        return None


def extract_vin(text: str) -> str | None:
    m = VIN_RE.search(text.upper())
    return m.group(1) if m else None


def extract_year(text: str) -> int | None:
    return _first_year(text)


def extract_trailer_length(text: str) -> int | None:
    m = TRAILER_LEN_RE.search(text)
    return int(m.group(1)) if m else None


def _kw_match(text: str, table: dict[str, list[str]]) -> str | None:
    t = text.lower()
    for key, keys in table.items():
        for k in keys:
            if k in t:
                return key
    return None


def extract_trailer_walls(text: str) -> str | None:
    return _kw_match(text, TRAILER_WALL_KEYWORDS)


def extract_trailer_door(text: str) -> str | None:
    return _kw_match(text, TRAILER_DOOR_KEYWORDS)


def extract_trailer_suspension(text: str) -> str | None:
    return _kw_match(text, TRAILER_SUSPENSION_KEYWORDS)


def classify_category(title: str, description: str = "") -> str:
    """Heuristic: truck_sleeper | truck_daycab | trailer_dryvan_53 | trailer_reefer | other."""
    t = f"{title} {description}".lower()
    if any(k in t for k in ("reefer", "refrigerated", "thermo king", "carrier unit")):
        return "trailer_reefer"
    if any(k in t for k in ("dry van", "dryvan", "53' van", "53ft van", "53 foot van")):
        return "trailer_dryvan_53"
    if "day cab" in t or "daycab" in t:
        return "truck_daycab"
    if any(k in t for k in ("sleeper", "condo", "72\"", "72in", "raised roof")):
        return "truck_sleeper"
    # fall back by model keywords
    for m in MODEL_KEYWORDS:
        if f" {m} " in f" {t} ":
            return "truck_sleeper"
    if "trailer" in t:
        return "trailer_dryvan_53"
    return "other"


def autofill_from_text(title: str, description: str = "") -> dict:
    """Bulk-extract all known fields from free text. Used by paste-URL importer."""
    text = f"{title}\n{description}"
    out = {
        "year": extract_year(text),
        "make": extract_make(text),
        "model": extract_model(text),
        "engine": extract_engine(text),
        "mileage": extract_mileage(text),
        "vin": extract_vin(text),
        "asking_price_cents": extract_price(text),
        "category": classify_category(title, description),
    }
    if out["category"] in ("trailer_dryvan_53", "trailer_reefer"):
        out["trailer_length_ft"] = extract_trailer_length(text)
        out["trailer_walls"] = extract_trailer_walls(text)
        out["trailer_door"] = extract_trailer_door(text)
        out["trailer_suspension"] = extract_trailer_suspension(text)
    return out
