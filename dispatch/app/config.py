import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////data/dispatch.db")

DISPATCH_USER = os.getenv("DISPATCH_USER", "dispatcher")
DISPATCH_PASS = os.getenv("DISPATCH_PASS", "change-me")

# --- Integration keys (all optional; blank means "degrade gracefully") ---
ORS_API_KEY = os.getenv("ORS_API_KEY", "").strip()
OSRM_URL = os.getenv("OSRM_URL", "").strip().rstrip("/")
EIA_API_KEY = os.getenv("EIA_API_KEY", "").strip()
FMCSA_WEBKEY = os.getenv("FMCSA_WEBKEY", "").strip()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()

# USDA AMS MyMarketNews (MARS) — free key for produce truck-rate seeds.
# https://mymarketnews.ams.usda.gov/ -> request an API key, then point
# USDA_TRUCK_REPORT_SLUG at a truck-rate report and USDA_RPM_FIELD at the
# field that holds a per-mile rate. Leave blank to use built-in reference rates.
USDA_API_KEY = os.getenv("USDA_API_KEY", "").strip()
USDA_TRUCK_REPORT_SLUG = os.getenv("USDA_TRUCK_REPORT_SLUG", "").strip()
USDA_RPM_FIELD = os.getenv("USDA_RPM_FIELD", "avg_mileage_rate").strip()
USDA_EQUIPMENT = os.getenv("USDA_EQUIPMENT", "reefer").strip()

# Model used for the negotiation letter. Opus 4.8 is the current default.
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-8")


def _int(name: str, default: int) -> int:
    try:
        return int(float(os.getenv(name, str(default))))
    except (ValueError, TypeError):
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (ValueError, TypeError):
        return default


# --- Truck economics defaults (overridable per-load via the /settings page) ---
DEFAULT_MPG = _float("DEFAULT_MPG", 6.5)
FIXED_MONTHLY_CENTS = _int("FIXED_MONTHLY_CENTS", 900000)   # insurance + truck note + permits
AVG_MONTHLY_MILES = _int("AVG_MONTHLY_MILES", 10000)
MAINT_CPM_CENTS = _int("MAINT_CPM_CENTS", 18)               # maintenance + tires per mile
TARGET_MARGIN_PCT = _int("TARGET_MARGIN_PCT", 30)
DEFAULT_DIESEL_CPG = _int("DEFAULT_DIESEL_CPG", 420)        # cents per gallon

DATA_DIR = os.getenv("DATA_DIR", "/data")

EQUIPMENT_TYPES = ["van", "reefer", "flatbed"]
