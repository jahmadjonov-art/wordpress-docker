from app.scoring import broker_rating


def test_clean_load_nudges_up():
    d = broker_rating.outcome_delta("on_time", "yes", "yes", tonu=False)
    assert d == 25 + 20 + 10


def test_short_pay_and_tonu_drop_hard():
    d = broker_rating.outcome_delta("short", "no", "no", tonu=True)
    assert d == -80 - 50 - 60 - 100


def test_apply_clamps():
    assert broker_rating.apply(broker_rating.MAX_ELO, 500) == broker_rating.MAX_ELO
    assert broker_rating.apply(broker_rating.MIN_ELO, -500) == broker_rating.MIN_ELO


def test_label_bands():
    assert broker_rating.label(1800) == "Excellent"
    assert broker_rating.label(1500) == "Neutral"
    assert broker_rating.label(1000) == "Avoid"
