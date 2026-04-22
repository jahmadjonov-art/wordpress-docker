import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////data/finance.db")

FINANCE_USER = os.getenv("FINANCE_USER", "driver")
FINANCE_PASS = os.getenv("FINANCE_PASS", "change-me")

CRAIGSLIST_METROS = [
    m.strip()
    for m in os.getenv(
        "CRAIGSLIST_METROS",
        "dallas,houston,atlanta,chicago,losangeles,memphis,oklahomacity",
    ).split(",")
    if m.strip()
]

SCRAPE_INTERVAL_HOURS = int(os.getenv("SCRAPE_INTERVAL_HOURS", "3"))
CA_OPERATION = os.getenv("CA_OPERATION", "false").lower() == "true"

DEFAULT_BUCKETS = [
    {"name": "Truck", "target": int(os.getenv("TARGET_TRUCK", "50000"))},
    {"name": "Trailer", "target": int(os.getenv("TARGET_TRAILER", "22000"))},
    {"name": "Taxes, title & IRP plates", "target": int(os.getenv("TARGET_TAXES_PLATES", "4500"))},
    {"name": "Authority & compliance", "target": int(os.getenv("TARGET_AUTHORITY", "2200"))},
    {"name": "Insurance down payment", "target": int(os.getenv("TARGET_INSURANCE_DOWN", "5000"))},
    {"name": "Equipment & tools", "target": int(os.getenv("TARGET_EQUIPMENT", "3500"))},
    {"name": "Operating reserve (8 wk)", "target": int(os.getenv("TARGET_OPERATING_RESERVE", "18000"))},
    {"name": "Contingency (10%)", "target": int(os.getenv("TARGET_CONTINGENCY", "10500"))},
]

DATA_DIR = "/data"
RAW_HTML_DIR = "/data/raw_html"
