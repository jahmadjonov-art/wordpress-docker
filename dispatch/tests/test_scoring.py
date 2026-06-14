from app import models
from app.scoring.load import score_load


def _mk(db, rpm_cents, loaded=1000.0):
    l = models.Load(
        origin_city="Dallas", origin_state="TX", dest_city="Atlanta", dest_state="GA",
        equipment="van", loaded_miles=loaded, deadhead_miles=0.0,
        rate_total_cents=rpm_cents * int(loaded // 100) * 100,
        rate_per_mile_cents=rpm_cents,
    )
    db.add(l)
    db.commit()
    db.refresh(l)
    return l


def test_high_rate_scores_above_median(db, settings):
    # build a market around 200 cpm
    for rpm in (190, 200, 200, 205, 210):
        _mk(db, rpm)
    hot = _mk(db, 280)  # well above median
    res = score_load(db, hot, settings, diesel_cpg=400)
    assert res.median_rpm_cents == 200
    assert res.score > 50
    assert res.suggested_target_rate_cents is not None


def test_low_rate_scores_below_median(db, settings):
    for rpm in (200, 205, 210, 215, 220):
        _mk(db, rpm)
    cold = _mk(db, 120)
    res = score_load(db, cold, settings, diesel_cpg=400)
    assert res.score < 50


def test_score_is_clamped(db, settings):
    res_load = models.Load(
        origin_city="Dallas", origin_state="TX", dest_city="Atlanta", dest_state="GA",
        equipment="van", loaded_miles=1000.0, deadhead_miles=2000.0,  # absurd deadhead
        rate_total_cents=10000, rate_per_mile_cents=10,
    )
    db.add(res_load)
    db.commit()
    db.refresh(res_load)
    res = score_load(db, res_load, settings, diesel_cpg=400)
    assert 0 <= res.score <= 100


def test_risk_keyword_penalty(db, settings):
    base = _mk(db, 200)
    base.notes = "Load requires lumper and tarp, no detention pay"
    db.commit()
    res = score_load(db, base, settings, diesel_cpg=400)
    labels = [lbl for lbl, _ in res.breakdown]
    assert any("detention" in l.lower() or "lumper" in l.lower() or "tarp" in l.lower() for l in labels)
