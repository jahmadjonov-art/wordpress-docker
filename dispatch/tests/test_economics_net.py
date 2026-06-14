from app import economics, models


def _load(**kw):
    base = dict(origin_city="A", origin_state="TX", dest_city="B", dest_state="GA",
                equipment="van", loaded_miles=1000.0, deadhead_miles=0.0,
                rate_total_cents=250000)
    base.update(kw)
    return models.Load(**base)


def test_net_revenue_subtracts_lumper_and_factoring(settings):
    settings.factoring_pct = 3.0
    l = _load(lumper_fee_cents=20000, payment_terms="net30")  # $200 lumper, factored
    net = economics.net_revenue_cents(l, settings)
    # 250000 - 20000 lumper - 3% of 250000 (7500) = 222500
    assert net == 250000 - 20000 - 7500


def test_quickpay_cheaper_than_net30(settings):
    settings.factoring_pct = 3.0
    net30 = economics.net_revenue_cents(_load(payment_terms="net30"), settings)
    quick = economics.net_revenue_cents(_load(payment_terms="quickpay"), settings)
    assert quick > net30  # 1% quick-pay fee beats 3% factoring


def test_hours_estimate_multiday(settings):
    settings.avg_speed_mph = 50.0
    h = economics.hours_estimate(_load(loaded_miles=1300.0), settings)
    assert h is not None
    # 1300/50 = 26h driving -> ceil(26/11)=3 days, on-duty > 14
    assert h.days == 3
    assert h.over_single_day is True


def test_hours_estimate_single_day(settings):
    h = economics.hours_estimate(_load(loaded_miles=400.0, deadhead_miles=0.0), settings)
    assert h.days == 1
    assert h.over_single_day is False
