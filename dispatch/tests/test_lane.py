from app import models
from app.scoring import lane


def _mk(db, o_state, d_state, equipment, rpm_cents):
    l = models.Load(
        origin_city="O", origin_state=o_state, dest_city="D", dest_state=d_state,
        equipment=equipment, loaded_miles=1000.0, rate_total_cents=rpm_cents * 10,
        rate_per_mile_cents=rpm_cents,
    )
    db.add(l)
    db.commit()
    db.refresh(l)
    return l


def test_lane_key_uses_regions():
    l = models.Load(origin_city="Dallas", origin_state="TX", dest_city="Atlanta",
                     dest_state="GA", equipment="van")
    # TX -> SC region, GA -> SE region
    assert lane.lane_key(l) == "van|SC|SE"


def test_compute_lane_stats_median(db):
    for rpm in (200, 220, 240, 260, 300):  # TX->GA van
        _mk(db, "TX", "GA", "van", rpm)
    n = lane.compute_lane_stats(db)
    assert n == 1
    stat = db.query(models.LaneStat).one()
    assert stat.sample_count == 5
    assert stat.median_rpm_cents == 240


def test_find_comps_widens_when_thin(db):
    # one exact-lane load (TX->GA), but several same-equipment+origin-region loads
    target = _mk(db, "TX", "GA", "van", 250)
    for rpm in (210, 230, 240, 260):  # TX (SC) origin, other destinations
        _mk(db, "TX", "FL", "van", rpm)
    comps = lane.find_comps(db, target)
    # exact lane had <5, so it widened to same-equipment+origin-region
    assert len(comps) >= 4
