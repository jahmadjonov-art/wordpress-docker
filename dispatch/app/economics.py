"""Cost-per-mile and profit model.

Computes what a load actually costs to run (fuel + maintenance + a slice of
fixed monthly overhead) so we can turn a flat rate into an honest profit number
and a "what rate do I need" target. All money is in integer cents.
"""
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


def target_rate_cents(cost_cents: int, settings: models.Settings) -> int:
    """The all-in rate that hits the configured profit margin on top of cost.

    margin_pct is profit as a fraction of revenue, so
    revenue = cost / (1 - margin_pct/100).
    """
    pct = max(0, min(95, settings.target_margin_pct)) / 100.0
    if pct >= 1:
        return cost_cents
    return int(round(cost_cents / (1 - pct)))
