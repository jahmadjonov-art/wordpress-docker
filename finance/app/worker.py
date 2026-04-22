"""APScheduler worker: runs scrapers + nightly market recompute + snapshot."""
import logging
import signal
import time
from datetime import date
from apscheduler.schedulers.blocking import BlockingScheduler

from . import config
from .db import SessionLocal, init_db
from .scrapers import craigslist as cl
from .scrapers import truckpaper, trucktrader, mylittlesalesman
from .scoring.market import compute_cohort_stats
from .scoring.engine import rescore_all
from . import models
from .summary import current_balance_cents

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
log = logging.getLogger("finance.worker")


def job_scrape_craigslist():
    with SessionLocal() as db:
        result = cl.run(db)
        log.info("craigslist: %s", result)


def job_scrape_truckpaper():
    with SessionLocal() as db:
        result = truckpaper.run(db)
        log.info("truckpaper: %s", result)


def job_scrape_trucktrader():
    with SessionLocal() as db:
        result = trucktrader.run(db)
        log.info("trucktrader: %s", result)


def job_scrape_mylittlesalesman():
    with SessionLocal() as db:
        result = mylittlesalesman.run(db)
        log.info("mylittlesalesman: %s", result)


def job_recompute_market():
    with SessionLocal() as db:
        n = compute_cohort_stats(db)
        log.info("market: %d cohorts recomputed", n)
        rescored = rescore_all(db)
        log.info("rescored %d active listings", rescored)


def job_snapshot_savings():
    with SessionLocal() as db:
        balance = current_balance_cents(db)
        db.add(models.SavingsSnapshot(as_of=date.today(), balance_cents=balance, source="derived"))
        db.commit()
        log.info("snapshot: balance=%d", balance)


def main():
    init_db()
    sched = BlockingScheduler(timezone="UTC")
    sched.add_job(
        job_scrape_craigslist,
        "interval",
        hours=config.SCRAPE_INTERVAL_HOURS,
        next_run_time=None,
        id="scrape_craigslist",
    )
    sched.add_job(job_recompute_market, "cron", hour=9, minute=0, id="recompute_market")
    sched.add_job(job_snapshot_savings, "cron", hour=12, minute=0, day_of_week="sun", id="snapshot_savings")

    sched.add_job(job_scrape_truckpaper, "interval", hours=config.SCRAPE_INTERVAL_HOURS, id="scrape_truckpaper")
    sched.add_job(job_scrape_trucktrader, "interval", hours=config.SCRAPE_INTERVAL_HOURS, id="scrape_trucktrader")
    sched.add_job(job_scrape_mylittlesalesman, "interval", hours=config.SCRAPE_INTERVAL_HOURS, id="scrape_mylittlesalesman")

    # kick off once at boot
    sched.add_job(job_scrape_craigslist, "date", id="bootstrap_scrape")
    sched.add_job(job_scrape_truckpaper, "date", id="bootstrap_truckpaper")
    sched.add_job(job_scrape_trucktrader, "date", id="bootstrap_trucktrader")
    sched.add_job(job_scrape_mylittlesalesman, "date", id="bootstrap_mylittlesalesman")
    sched.add_job(job_recompute_market, "date", id="bootstrap_market")

    def _shutdown(signum, frame):
        log.info("shutting down scheduler")
        sched.shutdown(wait=False)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    log.info(
        "scheduler starting — craigslist every %dh, metros=%s",
        config.SCRAPE_INTERVAL_HOURS,
        ",".join(config.CRAIGSLIST_METROS),
    )
    sched.start()


if __name__ == "__main__":
    main()
