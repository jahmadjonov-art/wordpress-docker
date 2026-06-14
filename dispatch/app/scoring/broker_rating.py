"""Broker reliability rating — an Elo-style score that drifts on logged outcomes.

Reborn from the (removed) chess bot's rating idea: instead of game results, the
broker gains or loses points as the user logs how a completed load actually went
(paid on time / short / detention honored / truck-ordered-not-used). The score
seeds at 1500 and feeds the load score, replacing a blunt authority-only check
with something that learns from the user's real experience.
"""

START_ELO = 1500
MIN_ELO = 0
MAX_ELO = 2500

# Outcome deltas (additive). Tuned so a clean load nudges up modestly and a
# burn (short pay, TONU) drops hard.
PAID_DELTA = {
    "on_time": 25,
    "late": -40,
    "short": -80,
    "unpaid": -150,
}
DETENTION_DELTA = {"yes": 20, "no": -50, "na": 0}
RATE_ACCURATE_DELTA = {"yes": 10, "no": -60, "na": 0}
TONU_DELTA = -100


def outcome_delta(paid_timing: str, detention_honored: str | None,
                  rate_accurate: str | None, tonu: bool) -> int:
    delta = PAID_DELTA.get(paid_timing, 0)
    delta += DETENTION_DELTA.get(detention_honored or "na", 0)
    delta += RATE_ACCURATE_DELTA.get(rate_accurate or "na", 0)
    if tonu:
        delta += TONU_DELTA
    return delta


def apply(current_elo: int, delta: int) -> int:
    return max(MIN_ELO, min(MAX_ELO, current_elo + delta))


def label(elo: int) -> str:
    if elo >= 1750:
        return "Excellent"
    if elo >= 1600:
        return "Good"
    if elo >= 1450:
        return "Neutral"
    if elo >= 1250:
        return "Caution"
    return "Avoid"
