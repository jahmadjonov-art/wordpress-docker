from app import economics, models


def _load(loaded=1000.0, deadhead=100.0, rate_cents=250000):
    return models.Load(
        origin_city="Dallas", origin_state="TX",
        dest_city="Atlanta", dest_state="GA",
        equipment="van", loaded_miles=loaded, deadhead_miles=deadhead,
        rate_total_cents=rate_cents,
    )


def test_estimate_cost_components(settings):
    # 6.5 mpg, 18 cpm maint, 9000.00 fixed / 10000 mi => 90 cpm fixed
    cost = economics.estimate_cost(_load(1000, 100), settings, diesel_cpg=400)
    assert cost.total_miles == 1100
    # fuel: 1100/6.5 = 169.23 gal * 400c = 67692c
    assert cost.fuel_cents == round(1100 / 6.5 * 400)
    # maintenance: 1100 * 18 = 19800
    assert cost.maintenance_cents == 1100 * 18
    # fixed: 1100 * (900000/10000=90) = 99000
    assert cost.fixed_cents == 1100 * 90
    assert cost.cost_cents == cost.fuel_cents + cost.maintenance_cents + cost.fixed_cents
    assert cost.cost_per_mile_cents == round(cost.cost_cents / 1100)


def test_estimate_cost_zero_miles(settings):
    cost = economics.estimate_cost(_load(0, 0), settings, diesel_cpg=400)
    assert cost.cost_cents == 0
    assert cost.cost_per_mile_cents == 0


def test_target_rate_hits_margin(settings):
    settings.target_margin_pct = 30
    # cost 70000 -> revenue 100000 yields exactly 30% margin
    assert economics.target_rate_cents(70000, settings) == 100000


def test_target_rate_zero_cost(settings):
    assert economics.target_rate_cents(0, settings) == 0
