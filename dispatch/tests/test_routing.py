from app.integrations import routing


def test_haversine_known_distance():
    # Dallas (32.78,-96.80) -> Atlanta (33.75,-84.39) ~ 720 miles straight line
    miles = routing.haversine_miles((32.78, -96.80), (33.75, -84.39))
    assert 700 < miles < 740


def test_road_miles_fallback_uses_road_factor(monkeypatch):
    # no ORS key / no OSRM -> haversine * 1.2
    monkeypatch.setattr(routing.config, "ORS_API_KEY", "")
    monkeypatch.setattr(routing.config, "OSRM_URL", "")
    miles, source = routing.road_miles((32.78, -96.80), (33.75, -84.39))
    assert source == "haversine"
    straight = routing.haversine_miles((32.78, -96.80), (33.75, -84.39))
    assert abs(miles - straight * routing.ROAD_FACTOR) < 0.01
