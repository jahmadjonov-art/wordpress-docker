from datetime import date

from app import models
from app.scoring import reference


def test_seed_overrides_builtin_reference(db):
    # no seed -> built-in van baseline
    assert reference.seed_base_cents(db, "van", "TX") is None
    builtin, _ = reference.reference_rpm_cents("van", None, "TX")
    assert builtin == reference.BASELINE_RPM_CENTS["van"]

    # add a US seed for van -> seed_base_cents returns it
    db.add(models.ReferenceRate(equipment="van", region="US", rpm_cents=210, source="usda_ams"))
    db.commit()
    assert reference.seed_base_cents(db, "van", "TX") == 210

    # and reference_rpm_cents honors the override
    seeded, _ = reference.reference_rpm_cents("van", None, "TX", base_override=210)
    assert seeded == 210
