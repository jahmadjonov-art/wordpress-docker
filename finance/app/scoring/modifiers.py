"""Scoring modifier tables. Kept as plain dicts so they're easy to tune."""

# Make / model modifiers for Class 8 sleeper trucks.
# Matched by (make_lower, model_contains, engine_contains, year_range).
TRUCK_MODEL_MODS = [
    # (make, model_sub, engine_sub, year_min, year_max, mod, label)
    ("freightliner", "cascadia", "dd15", 2018, 2099, +8, "Cascadia DD15 2018+ (best resale, strong MPG)"),
    ("freightliner", "cascadia", "dd15", 2014, 2017, +5, "Cascadia DD15 2014-2017 (known quantity)"),
    ("freightliner", "cascadia", "",     2014, 2099, +3, "Cascadia (parts everywhere)"),
    ("kenworth",     "t680",     "x15",  2014, 2099, +6, "T680 X15 (strong resale, driver pick)"),
    ("kenworth",     "t680",     "mx",   2014, 2099, +2, "T680 MX-13 (watch EGR cooler pre-2017)"),
    ("peterbilt",    "579",      "x15",  2014, 2099, +6, "Peterbilt 579 X15 (strong resale)"),
    ("peterbilt",    "579",      "mx",   2014, 2099, +2, "Peterbilt 579 MX-13"),
    ("volvo",        "vnl",      "d13",  2018, 2099, +3, "VNL D13 2018+"),
    ("volvo",        "vnl",      "d13",  2014, 2017, -2, "VNL D13 2014-2017 (turbo actuator, DEF head issues)"),
    ("international","lt",       "a26",  2017, 2099, -3, "International LT A26 (unproven long-term)"),
    ("international","prostar",  "maxxforce", 2010, 2014, -20, "ProStar Maxxforce (EGR disaster — avoid)"),
    ("mack",         "anthem",   "mp8",  2017, 2099, -1, "Mack Anthem (service network weak outside East)"),
    ("western star", "5700",     "dd15", 2014, 2099, +2, "Western Star 5700 DD15 (niche but serviceable)"),
]

# Emissions-era modifiers (year-based hard cost).
EMISSIONS_ERAS = [
    # (year_min, year_max, mod_non_ca, mod_ca, label)
    (0,    2006, +3,  -15, "Pre-2007 (no DPF) — reliable, CARB-restricted"),
    (2007, 2009, -4,  -15, "2007-2009 DPF no-DEF — regen headaches, CARB-restricted"),
    (2010, 2012, -8,  -8,  "2010-2012 first-gen SCR/DEF — worst era for reliability"),
    (2013, 2016,  0,   0,  "2013-2016 refined SCR — baseline"),
    (2017, 2099, +4,  +4,  "2017+ GHG17 — best fuel economy, warranty tail"),
]

TRANSMISSION_MODS = {
    "manual":    (+2, "Manual (cheap to maintain)"),
    "automated": ( 0, "Automated (I-Shift, mDrive, UltraShift+)"),
    "allison":   (-3, "Allison auto (heavy, resale concern in sleeper)"),
}


def mileage_band(miles: int | None) -> str | None:
    if miles is None:
        return None
    if miles < 400_000:
        return "<400k"
    if miles < 600_000:
        return "400-600k"
    if miles < 800_000:
        return "600-800k"
    if miles < 1_000_000:
        return "800k-1M"
    return ">1M"


TRUCK_MILEAGE_MODS = {
    "<400k":  (+3, "Low miles <400k"),
    "400-600k": ( 0, "400-600k miles (normal used)"),
    "600-800k": (-3, "600-800k miles"),
    "800k-1M":  (-5, "800k-1M miles (high)"),
    ">1M":      (-10, ">1M miles (end of life without in-frame)"),
}

# Condition keyword regex -> (mod, label, cap per group)
# Parsed from title + description. Caps apply per "group" to prevent stacking.
TRUCK_CONDITION_KEYWORDS = [
    # positive
    (r"\b(in[- ]?frame|fresh\s+rebuild|recent\s+overhaul|new\s+engine)\b", +8, "in-frame/rebuild", "engine_work"),
    (r"\bnew\s+clutch\b",     +2, "new clutch", "minor_work"),
    (r"\bnew\s+injectors?\b", +2, "new injectors", "minor_work"),
    (r"\bnew\s+turbo\b",      +2, "new turbo", "minor_work"),
    (r"\b(new\s+virgin\s+rubber|new\s+tires|new\s+steers|new\s+drives)\b", +3, "new tires", "tires"),
    (r"\b(carb\s+compliant|ca\s+legal|california\s+legal)\b", +4, "CARB compliant", "compliance"),
    (r"\bclean\s+title\b",    +2, "clean title", "title"),
    (r"\b(apu|espar|thermo\s*king\s*tripac)\b", +2, "APU", "amenities"),
    # negative
    (r"\b(salvage|rebuilt)\s+title\b", -25, "salvage/rebuilt title", "title"),
    (r"\b(needs\s+work|as[- ]is|mechanic\s+special|not\s+running|no\s+start)\b", -15, "needs work / as-is", "condition"),
    (r"\b(deleted|delete|tuned|no\s+dpf|dpf\s+delete|egr\s+delete)\b", -10, "emissions deleted (federal fine risk)", "emissions_delete"),
]

TRUCK_KEYWORD_CAPS = {
    "engine_work": +8,
    "minor_work":  +6,
    "tires":       +3,
    "compliance":  +4,
    "title":       +2,
    "amenities":   +4,
    "condition":  -15,
    "emissions_delete": -10,
}

# ---- Trailer modifiers ----

TRAILER_AGE_MODS = [
    (2020, 2099, +5, "2020+ trailer"),
    (2015, 2019, +3, "2015-2019 trailer"),
    (2010, 2014,  0, "2010-2014 trailer"),
    (2005, 2009, -4, "2005-2009 trailer (DOT risk)"),
    (0,    2004, -8, "pre-2005 trailer (brakes/drums risk)"),
]

TRAILER_WALL_MODS = {
    "composite":              (+5, "composite / plate walls (Wabash DuraPlate / Everest / 4000D-X)"),
    "aluminum_sheet_post":    (-2, "sheet-and-post aluminum"),
    "aluminum_smooth":        ( 0, "smooth aluminum skin"),
}

TRAILER_DOOR_MODS = {
    "swing":  (+3, "swing doors (shipper default)"),
    "rollup": (-4, "roll-up door (many DCs refuse)"),
}

TRAILER_SUSPENSION_MODS = {
    "air":    (+5, "air ride"),
    "spring": (-10, "spring ride (limits freight)"),
}

TRAILER_CONDITION_KEYWORDS = [
    (r"\b(new\s+virgin\s+rubber|new\s+tires\s+all\s+around|8\s+new\s+tires)\b", +4, "new tires", "tires"),
    (r"\b(recent\s+recaps|recaps)\b", 0, "recent recaps", "tires"),
    (r"\b(tires\s+need|low\s+tread|bald\s+tires)\b", -5, "tires need replaced", "tires"),
    (r"\b(new\s+floor|no\s+soft\s+spots|scuffed\s+floor)\b", +3, "floor good", "floor"),
    (r"\b(soft\s+spots|needs\s+floor|rotted\s+floor)\b", -8, "floor needs work", "floor"),
    (r"\b(fresh\s+dot|current\s+dot|passed\s+dot|just\s+dot[- ]ed)\b", +4, "fresh DOT inspection", "dot"),
    (r"\bdot\s+ready\b", +2, "DOT ready", "dot"),
    (r"\b(needs\s+dot|out\s+of\s+dot|no\s+dot)\b", -6, "needs DOT", "dot"),
    (r"\b(new\s+roof|translucent\s+roof)\b", +2, "roof good", "roof"),
    (r"\b(roof\s+leaks|needs\s+roof)\b", -10, "roof needs work", "roof"),
]

TRAILER_KEYWORD_CAPS = {
    "tires": +4,
    "floor": +3,
    "dot":   +4,
    "roof":  +2,
}

# Data completeness penalties (applied to both categories)
COMPLETENESS_PENALTIES = [
    ("year",     -5, "missing year"),
    ("mileage",  -5, "missing mileage (truck only)"),
    ("vin",      -3, "missing VIN"),
    ("engine",   -4, "engine not specified (truck only)"),
]
