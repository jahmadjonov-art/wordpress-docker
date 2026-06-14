"""Score a load 0-100 (bad -> good) and compute its negotiation numbers.

Formula mirrors finance/app/scoring/truck.py:
  base = 50 + clamp(±50, (rpm - benchmark)/benchmark * 100)
then signed modifier deltas, then clamp to 0-100. The benchmark is the user's
own lane median once enough comps exist, otherwise a seasonally-adjusted
national reference rate (so the score is useful on load #1). Alongside the score
we return true-net profit, deadhead-adjusted RPM, profit-per-hour, and the
suggested target rate.
"""
import statistics
from dataclasses import dataclass

from sqlalchemy.orm import Session

from .. import models, economics
from . import modifiers, reference, broker_rating
from .lane import find_comps


@dataclass
class ScoreResult:
    score: int
    confidence: float
    comp_count: int
    median_rpm_cents: int | None        # benchmark used (lane median or reference)
    est_cost_cents: int | None
    est_profit_cents: int | None         # uses true-net revenue
    suggested_target_rate_cents: int | None
    net_revenue_cents: int | None
    deadhead_adj_rpm_cents: int | None
    profit_per_hour_cents: int | None
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

    # --- benchmark: lane comps if we have enough, else seasonal reference ---
    comps = find_comps(db, load)
    comp_count = len(comps)
    benchmark = None
    if comp_count >= reference.MIN_COMPS_FOR_LANE:
        benchmark = int(statistics.median(comps))
        confidence = min(1.0, comp_count / 15.0)
        bench_label = f"Rate vs lane median of {comp_count} loads"
    else:
        seed = reference.seed_base_cents(db, load.equipment, load.origin_state)
        ref, season_note = reference.reference_rpm_cents(
            load.equipment, load.pickup_date, load.origin_state, base_override=seed
        )
        benchmark = ref
        confidence = 0.25
        src = "USDA/seed" if seed else "national"
        bench_label = f"Rate vs {load.equipment} {src} reference (thin lane history)"
        if season_note:
            breakdown.append((season_note, 0))

    if load.rate_per_mile_cents and benchmark:
        ratio = (load.rate_per_mile_cents - benchmark) / benchmark
        base = 50 + max(-50, min(50, int(ratio * 100)))
        breakdown.append((f"{bench_label} ({benchmark/100:.2f}/mi)", base - 50))
    else:
        base = 50
        breakdown.append(("No rate/mile to benchmark — neutral base", 0))
        confidence = 0.1

    score = base

    # --- cost / true-net profit / target rate ---
    cost = economics.estimate_cost(load, settings, diesel_cpg)
    est_cost_cents = cost.cost_cents if cost.total_miles else None
    net_revenue = economics.net_revenue_cents(load, settings)
    est_profit_cents = None
    target_rate = None
    if est_cost_cents is not None:
        target_rate = economics.target_rate_cents(est_cost_cents, settings)
        if net_revenue is not None:
            est_profit_cents = net_revenue - est_cost_cents

    # surface that accessorials/financing were deducted
    if load.rate_total_cents is not None and net_revenue is not None and net_revenue != load.rate_total_cents:
        breakdown.append((
            f"True-net after lumper/financing ({net_revenue/100:.0f} of {load.rate_total_cents/100:.0f})", 0
        ))

    # --- deadhead-adjusted RPM (rate over loaded + deadhead) ---
    total_miles = (load.loaded_miles or 0.0) + (load.deadhead_miles or 0.0)
    deadhead_adj_rpm = None
    if load.rate_total_cents and total_miles > 0:
        deadhead_adj_rpm = int(round(load.rate_total_cents / total_miles))

    # --- hours-of-service: profit per on-duty hour + multi-day flag ---
    hours = economics.hours_estimate(load, settings)
    profit_per_hour = None
    if hours and est_profit_cents is not None and hours.on_duty_hours > 0:
        profit_per_hour = int(round(est_profit_cents / hours.on_duty_hours))
        if hours.over_single_day:
            breakdown.append((f"Multi-day: ~{hours.days} HOS day(s), {hours.on_duty_hours:.0f}h on-duty", 0))

    # --- deadhead band ---
    if load.loaded_miles and load.loaded_miles > 0:
        dh_ratio = (load.deadhead_miles or 0.0) / load.loaded_miles
        delta, label = _band(dh_ratio, modifiers.DEADHEAD_BANDS)
        if label:
            score += delta
            breakdown.append((label, delta))

    # --- margin vs target band (on true net) ---
    if est_profit_cents is not None and net_revenue:
        actual_margin_pct = 100.0 * est_profit_cents / net_revenue
        gap = actual_margin_pct - settings.target_margin_pct
        delta, label = _band(gap, modifiers.MARGIN_BANDS)
        if label:
            score += delta
            breakdown.append((f"{label} ({actual_margin_pct:.0f}% vs {settings.target_margin_pct}%)", delta))

    # --- broker reliability (learned Elo) + authority ---
    if broker is not None:
        if broker.allowed_to_operate == "N":
            d, lbl = modifiers.BROKER_INACTIVE_PENALTY
            score += d
            breakdown.append((lbl, d))
        elif broker.allowed_to_operate == "Y":
            d, lbl = modifiers.BROKER_OK_BONUS
            score += d
            breakdown.append((lbl, d))
        if broker.outcomes_count > 0:
            rel = _reliability_delta(broker.reliability_elo)
            if rel:
                score += rel
                breakdown.append((
                    f"Broker reliability {broker_rating.label(broker.reliability_elo)} "
                    f"({broker.reliability_elo}, {broker.outcomes_count} loads)", rel
                ))

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
        median_rpm_cents=benchmark,
        est_cost_cents=est_cost_cents,
        est_profit_cents=est_profit_cents,
        suggested_target_rate_cents=target_rate,
        net_revenue_cents=net_revenue,
        deadhead_adj_rpm_cents=deadhead_adj_rpm,
        profit_per_hour_cents=profit_per_hour,
        breakdown=breakdown,
    )


def _reliability_delta(elo: int) -> int:
    """Map a broker's reliability Elo to a score delta (±, capped)."""
    return max(-20, min(12, round((elo - broker_rating.START_ELO) / 25)))
