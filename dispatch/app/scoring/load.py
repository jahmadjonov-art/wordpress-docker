"""Score a load 0-100 (bad -> good) and compute its negotiation numbers.

Formula mirrors finance/app/scoring/truck.py:
  base = 50 + clamp(+/-50, (rpm - lane_median)/lane_median * 100)
then signed modifier deltas, then clamp to 0-100. Alongside the score we return
the cost, profit, and the suggested target rate (the "how much can we squeeze"
number) so the UI and the AI letter can use them.
"""
import statistics
from dataclasses import dataclass

from sqlalchemy.orm import Session

from .. import models, economics
from . import modifiers
from .lane import find_comps


@dataclass
class ScoreResult:
    score: int
    confidence: float
    comp_count: int
    median_rpm_cents: int | None
    est_cost_cents: int | None
    est_profit_cents: int | None
    suggested_target_rate_cents: int | None
    breakdown: list[tuple[str, int]]


def _band(value: float, bands) -> tuple[int, str]:
    for lo, hi, delta, label in bands:
        if lo <= value < hi:
            return delta, label
    return 0, ""


def score_load(
    db: Session,
    load: models.Load,
    settings: models.Settings,
    diesel_cpg: int,
    broker: models.Broker | None = None,
) -> ScoreResult:
    breakdown: list[tuple[str, int]] = []

    # --- base: rate-per-mile vs lane median ---
    comps = find_comps(db, load)
    median_rpm = None
    comp_count = len(comps)
    if comps and load.rate_per_mile_cents:
        median_rpm = int(statistics.median(comps))
        ratio = (load.rate_per_mile_cents - median_rpm) / median_rpm if median_rpm else 0
        base = 50 + max(-50, min(50, int(ratio * 100)))
        breakdown.append((f"Rate vs lane median of {comp_count} loads ({median_rpm/100:.2f}/mi)", base - 50))
        confidence = min(1.0, comp_count / 15.0)
    else:
        base = 50
        breakdown.append(("No lane comps yet — neutral base", 0))
        confidence = 0.1

    score = base

    # --- cost / profit / target rate ---
    cost = economics.estimate_cost(load, settings, diesel_cpg)
    est_cost_cents = cost.cost_cents if cost.total_miles else None
    est_profit_cents = None
    target_rate = None
    if est_cost_cents is not None:
        target_rate = economics.target_rate_cents(est_cost_cents, settings)
        if load.rate_total_cents is not None:
            est_profit_cents = load.rate_total_cents - est_cost_cents

    # --- deadhead band ---
    if load.loaded_miles and load.loaded_miles > 0:
        dh_ratio = (load.deadhead_miles or 0.0) / load.loaded_miles
        delta, label = _band(dh_ratio, modifiers.DEADHEAD_BANDS)
        if label:
            score += delta
            breakdown.append((label, delta))

    # --- margin vs target band ---
    if est_profit_cents is not None and load.rate_total_cents:
        actual_margin_pct = 100.0 * est_profit_cents / load.rate_total_cents
        gap = actual_margin_pct - settings.target_margin_pct
        delta, label = _band(gap, modifiers.MARGIN_BANDS)
        if label:
            score += delta
            breakdown.append((f"{label} ({actual_margin_pct:.0f}% vs {settings.target_margin_pct}%)", delta))

    # --- broker authority ---
    if broker is not None:
        if broker.allowed_to_operate == "Y":
            delta, label = modifiers.BROKER_OK_BONUS
        else:
            delta, label = modifiers.BROKER_INACTIVE_PENALTY
        score += delta
        breakdown.append((label, delta))

    # --- risk keywords ---
    text = (load.notes or "").lower()
    for sub, delta, label in modifiers.RISK_KEYWORDS:
        if sub in text:
            score += delta
            breakdown.append((label, delta))

    # --- completeness ---
    for attr, penalty, label in modifiers.COMPLETENESS_PENALTIES:
        if not getattr(load, attr, None):
            score += penalty
            breakdown.append((label, penalty))

    score = max(0, min(100, score))

    return ScoreResult(
        score=score,
        confidence=confidence,
        comp_count=comp_count,
        median_rpm_cents=median_rpm,
        est_cost_cents=est_cost_cents,
        est_profit_cents=est_profit_cents,
        suggested_target_rate_cents=target_rate,
        breakdown=breakdown,
    )
