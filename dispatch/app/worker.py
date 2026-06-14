"""APScheduler worker: nightly fuel refresh + lane recompute + rescore.

Mirrors finance/app/worker.py. Runs as a separate container alongside the web
app, sharing the same SQLite volume.
"""
import logging
import signal
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler

from .db import SessionLocal, init_db
from .integrations import eia, usda
from .scoring.lane import compute_lane_stats
from .scoring.engine import rescore_all
from . import models

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
log = logging.getLogger("dispatch.worker")


def _record(job: str, detail: str):
    with SessionLocal() as db:
        db.add(models.JobRun(job=job, finished_at=datetime.utcnow(), detail=detail, status="ok"))
        db.commit()


def job_refresh_fuel():
    with SessionLocal() as db:
        cpg = eia.refresh(db)
        log.info("fuel: diesel now %d cpg", cpg)
    _record("refresh_fuel", f"diesel={cpg}cpg")


def job_refresh_produce():
    with SessionLocal() as db:
        n = usda.refresh(db)
        log.info("usda: %d produce rate rows -> reference", n)
    _record("refresh_produce", f"rows={n}")


def job_recompute_lanes():
    with SessionLocal() as db:
        n = compute_lane_stats(db)
        rescored = rescore_all(db)
        log.info("lanes: %d cohorts, %d loads rescored", n, rescored)
    _record("recompute_lanes", f"cohorts={n} rescored={rescored}")


def main():
    init_db()
    sched = BlockingScheduler(timezone="UTC")

    # nightly: refresh diesel + produce seeds, then recompute benchmarks + rescore
    sched.add_job(job_refresh_fuel, "cron", hour=8, minute=0, id="refresh_fuel")
    sched.add_job(job_refresh_produce, "cron", hour=8, minute=5, id="refresh_produce")
    sched.add_job(job_recompute_lanes, "cron", hour=8, minute=10, id="recompute_lanes")

    # kick once at boot
    sched.add_job(job_refresh_fuel, "date", id="bootstrap_fuel")
    sched.add_job(job_refresh_produce, "date", id="bootstrap_produce")
    sched.add_job(job_recompute_lanes, "date", id="bootstrap_lanes")

    def _shutdown(signum, frame):
        log.info("shutting down scheduler")
        sched.shutdown(wait=False)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    log.info("dispatch scheduler starting")
    sched.start()


if __name__ == "__main__":
    main()
