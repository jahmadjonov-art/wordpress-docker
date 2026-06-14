"""Cost-per-mile and profit model.

Computes what a load actually costs to run (fuel + maintenance + a slice of
fixed monthly overhead) so we can turn a flat rate into an honest profit number
and a "what rate do I need" target. All money is in integer cents.
"""
import math
from dataclasses import dataclass

from . import models


@dataclass
class CostEstimate:
    total_miles: float          # loaded + deadhead
    fuel_cents: int
    maintenance_cents: int
    fixed_cents: int
    cost_cents: int             # sum of the above
    cost_per_mile_cents: int    # cost_cents / total_miles (0 if no miles)


def fixed_cost_per_mile_cents(settings: models.Settings) -> float:
    """Fixed monthly overhead spread across average monthly miles."""
    if settings.avg_monthly_miles <= 0:
        return 0.0
    return settings.fixed_monthly_cents / settings.avg_monthly_miles


def estimate_cost(load: models.Load, settings: models.Settings, diesel_cpg: int) -> CostEstimate:
    """diesel_cpg = current diesel price in cents/gallon."""
    total_miles = (load.loaded_miles or 0.0) + (load.deadhead_miles or 0.0)
    if total_miles <= 0:
        return CostEstimate(0.0, 0, 0, 0, 0, 0)

    mpg = settings.mpg if settings.mpg and settings.mpg > 0 else 6.5
    gallons = total_miles / mpg
    fuel_cents = int(round(gallons * diesel_cpg))

    maintenance_cents = int(round(total_miles * settings.maint_cpm_cents))
    fixed_cents = int(round(total_miles * fixed_cost_per_mile_cents(settings)))

    cost_cents = fuel_cents + maintenance_cents + fixed_cents
    cpm = int(round(cost_cents / total_miles)) if total_miles else 0
    return CostEstimate(total_miles, fuel_cents, maintenance_cents, fixed_cents, cost_cents, cpm)


@dataclass
class HoursEstimate:
    drive_hours: float
    on_duty_hours: float        # driving + ~1.5h load/unload
    days: int                   # full HOS days (11h driving/day)
    over_single_day: bool       # can't legally run in one duty period


# How a load's pay terms translate to a financing cost, as a % of the rate.
# Net terms imply you float the cash (factoring/credit); quick-pay is a flat fee.
def financing_pct(payment_terms: str | None, settings: models.Settings) -> float:
    pt = (payment_terms or "").lower()
    if pt in ("net30", "net-30", ""):
        return settings.factoring_pct          # default assumption: you factor it
    if pt in ("net15", "net-15"):
        return settings.factoring_pct * 0.6
    if pt in ("quickpay", "quick-pay", "quick_pay"):
        return 1.0                              # typical quick-pay fee
    if pt in ("cod", "ach", "direct", "net7", "net-7"):
        return 0.0
    return settings.factoring_pct


def net_revenue_cents(load: models.Load, settings: models.Settings) -> int | None:
    """Rate minus accessorials the driver eats (lumper) and financing cost."""
    if load.rate_total_cents is None:
        return None
    fin = int(round(load.rate_total_cents * financing_pct(load.payment_terms, settings) / 100.0))
    lumper = load.lumper_fee_cents or 0
    return load.rate_total_cents - lumper - fin


def hours_estimate(load: models.Load, settings: models.Settings) -> HoursEstimate | None:
    total_miles = (load.loaded_miles or 0.0) + (load.deadhead_miles or 0.0)
    if total_miles <= 0:
        return None
    speed = settings.avg_speed_mph if settings.avg_speed_mph and settings.avg_speed_mph > 0 else 50.0
    drive_hours = total_miles / speed
    on_duty = drive_hours + 1.5
    days = max(1, math.ceil(drive_hours / 11.0))   # 11h driving limit per duty day
    return HoursEstimate(drive_hours, on_duty, days, on_duty > 14.0)


def target_rate_cents(cost_cents: int, settings: models.Settings) -> int:
    """The all-in rate that hits the configured profit margin on top of cost.

    margin_pct is profit as a fraction of revenue, so
    revenue = cost / (1 - margin_pct/100).
    """
    pct = max(0, min(95, settings.target_margin_pct)) / 100.0
    if pct >= 1:
        return cost_cents
    return int(round(cost_cents / (1 - pct)))
