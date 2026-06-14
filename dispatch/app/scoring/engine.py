"""Top-level entry: score a load and persist a LoadScore row.

Mirrors finance/app/scoring/engine.py (score_and_save / rescore_all).
"""
import json
from datetime import datetime
from sqlalchemy.orm import Session

from .. import models
from ..integrations import eia, fmcsa
from .load import score_load


def _settings(db: Session) -> models.Settings:
    s = db.get(models.Settings, 1)
    if s is None:  # defensive — init_db seeds this, but rescore may run early
        from .. import config
        s = models.Settings(
            id=1, mpg=config.DEFAULT_MPG, fixed_monthly_cents=config.FIXED_MONTHLY_CENTS,
            avg_monthly_miles=config.AVG_MONTHLY_MILES, maint_cpm_cents=config.MAINT_CPM_CENTS,
            target_margin_pct=config.TARGET_MARGIN_PCT,
        )
        db.add(s)
        db.commit()
    return s


def score_and_save(db: Session, load: models.Load) -> models.LoadScore:
    settings = _settings(db)
    diesel_cpg = eia.current_cpg(db)

    broker = None
    if load.broker_mc:
        broker = fmcsa.lookup(db, load.broker_mc)

    result = score_load(db, load, settings, diesel_cpg, broker)

    row = models.LoadScore(
        load_id=load.id,
        scored_at=datetime.utcnow(),
        score=result.score,
        confidence=result.confidence,
        lane_comp_count=result.comp_count,
        median_rpm_cents=result.median_rpm_cents,
        est_cost_cents=result.est_cost_cents,
        est_profit_cents=result.est_profit_cents,
        suggested_target_rate_cents=result.suggested_target_rate_cents,
        breakdown_json=json.dumps(result.breakdown),
    )
    db.add(row)
    db.commit()
    return row


def rescore_all(db: Session) -> int:
    count = 0
    for load in db.query(models.Load).filter(models.Load.status == "active").all():
        score_and_save(db, load)
        count += 1
    return count
