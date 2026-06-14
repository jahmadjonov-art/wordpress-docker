from datetime import date

from app import seasonality
from app.scoring import reference


def test_reefer_peak_in_produce_season():
    factor, note = seasonality.reefer_factor("reefer", date(2026, 6, 15), "MW")
    assert factor > 1.0
    assert note is not None


def test_van_unaffected_by_season():
    factor, note = seasonality.reefer_factor("van", date(2026, 6, 15), "SE")
    assert factor == 1.0 and note is None


def test_reference_reefer_higher_in_season():
    in_season, _ = reference.reference_rpm_cents("reefer", date(2026, 6, 1), "CA")
    off_season, _ = reference.reference_rpm_cents("reefer", date(2026, 12, 1), "CA")
    assert in_season > off_season


def test_reference_defaults_by_equipment():
    van, _ = reference.reference_rpm_cents("van", None, "TX")
    flat, _ = reference.reference_rpm_cents("flatbed", None, "TX")
    assert flat > van
