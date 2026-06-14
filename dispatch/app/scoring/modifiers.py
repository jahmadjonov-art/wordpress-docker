"""Tunable scoring tables for loads.

Mirrors the finance app's modifier-table pattern: each adjustment is a small
signed delta applied on top of the rate-vs-market base, then the score is
clamped to 0-100. Edit these numbers to retune without touching the formula.
"""

# Region buckets — coarse multi-state groupings used to build lane cohorts and
# to widen comps when an exact lane has too few samples.
REGION_BY_STATE = {
    # Northeast
    "ME": "NE", "NH": "NE", "VT": "NE", "MA": "NE", "RI": "NE", "CT": "NE",
    "NY": "NE", "NJ": "NE", "PA": "NE",
    # Southeast
    "DE": "SE", "MD": "SE", "DC": "SE", "VA": "SE", "WV": "SE", "NC": "SE",
    "SC": "SE", "GA": "SE", "FL": "SE", "KY": "SE", "TN": "SE", "AL": "SE",
    "MS": "SE", "AR": "SE", "LA": "SE",
    # Midwest
    "OH": "MW", "MI": "MW", "IN": "MW", "IL": "MW", "WI": "MW", "MN": "MW",
    "IA": "MW", "MO": "MW", "ND": "MW", "SD": "MW", "NE": "MW", "KS": "MW",
    # South Central / Texas
    "TX": "SC", "OK": "SC", "NM": "SC",
    # West
    "CO": "W", "WY": "W", "MT": "W", "ID": "W", "UT": "W", "AZ": "W", "NV": "W",
    # Pacific
    "CA": "PAC", "OR": "PAC", "WA": "PAC", "AK": "PAC", "HI": "PAC",
}


def region_for(state: str | None) -> str:
    return REGION_BY_STATE.get((state or "").strip().upper(), "OTH")


# --- Deadhead penalty: ratio of deadhead to loaded miles -> score delta ---
# (min_ratio, max_ratio, delta, label)
DEADHEAD_BANDS = [
    (0.0, 0.10, 5, "Minimal deadhead (<10%)"),
    (0.10, 0.20, 0, "Modest deadhead (10-20%)"),
    (0.20, 0.35, -8, "High deadhead (20-35%)"),
    (0.35, 999.0, -18, "Excessive deadhead (>35%)"),
]

# --- Profit margin vs target: actual margin% minus target margin% -> delta ---
# (min_gap_pts, max_gap_pts, delta, label)
MARGIN_BANDS = [
    (-999.0, -15.0, -25, "Margin far below target"),
    (-15.0, -5.0, -12, "Margin below target"),
    (-5.0, 5.0, 0, "Margin near target"),
    (5.0, 15.0, 10, "Margin above target"),
    (15.0, 999.0, 18, "Margin well above target"),
]

# --- Broker authority modifier ---
BROKER_OK_BONUS = (4, "Broker authority active (FMCSA)")
BROKER_INACTIVE_PENALTY = (-30, "Broker NOT authorized to operate (FMCSA)")

# --- Risk keywords in the notes (detention / accessorial traps) ---
# (substring, delta, label)
RISK_KEYWORDS = [
    ("no detention", -6, "Broker excludes detention pay"),
    ("driver assist", -5, "Driver-assist / hand unload"),
    ("lumper", -4, "Lumper fee risk"),
    ("multi stop", -4, "Multiple stops"),
    ("multi-stop", -4, "Multiple stops"),
    ("tarp", -4, "Tarping required"),
    ("hazmat", -3, "Hazmat"),
    ("team", -3, "Team load"),
    ("appointment only", -2, "Strict appointment windows"),
    ("quick pay", 3, "Quick pay offered"),
    ("detention pay", 3, "Detention pay included"),
]

# --- Completeness penalties for missing fields ---
# (attr, penalty, label)
COMPLETENESS_PENALTIES = [
    ("rate_total_cents", -10, "No rate provided"),
    ("loaded_miles", -10, "No mileage available"),
    ("broker_mc", -3, "No broker MC number"),
]
