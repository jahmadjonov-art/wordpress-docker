from app import models
from app.scoring import backhaul


def _mk(db, o, olat, olng, d, dlat, dlng, rate=200000, loaded=1000.0, equip="van"):
    l = models.Load(
        origin_city=o, origin_state="XX", dest_city=d, dest_state="YY",
        equipment=equip, loaded_miles=loaded, deadhead_miles=0.0,
        origin_lat=olat, origin_lng=olng, dest_lat=dlat, dest_lng=dlng,
        rate_total_cents=rate, rate_per_mile_cents=int(rate / loaded),
    )
    db.add(l)
    db.commit()
    db.refresh(l)
    return l


def test_finds_load_picking_up_near_drop(db):
    # headhaul Dallas -> Atlanta
    head = _mk(db, "Dallas", 32.78, -96.80, "Atlanta", 33.75, -84.39)
    # candidate picks up in Atlanta (same point) -> ~0 connect miles
    _mk(db, "Atlanta", 33.75, -84.39, "Memphis", 35.15, -90.05)
    # far-away candidate (Seattle) should NOT match
    _mk(db, "Seattle", 47.61, -122.33, "Portland", 45.52, -122.68)
    res = backhaul.find_backhauls(db, head, radius_miles=150)
    assert len(res) == 1
    assert res[0].load.origin_city == "Atlanta"
    assert res[0].connect_miles < 30


def test_round_trip_combines_economics(db):
    head = _mk(db, "Dallas", 32.78, -96.80, "Atlanta", 33.75, -84.39, rate=200000, loaded=780)
    _mk(db, "Atlanta", 33.75, -84.39, "Dallas", 32.78, -96.80, rate=180000, loaded=780)
    res = backhaul.find_backhauls(db, head, radius_miles=150)
    rt = backhaul.round_trip(head, res[0])
    assert rt is not None
    assert rt.total_rate_cents == 380000
    assert rt.rpm_cents > 0


def test_equipment_filter(db):
    head = _mk(db, "Dallas", 32.78, -96.80, "Atlanta", 33.75, -84.39, equip="reefer")
    _mk(db, "Atlanta", 33.75, -84.39, "Memphis", 35.15, -90.05, equip="van")  # wrong equip
    assert backhaul.find_backhauls(db, head, radius_miles=150) == []
