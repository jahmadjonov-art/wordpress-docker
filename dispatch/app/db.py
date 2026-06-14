import os
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from . import config

os.makedirs(config.DATA_DIR, exist_ok=True)

engine = create_engine(
    config.DATABASE_URL,
    connect_args={"check_same_thread": False} if config.DATABASE_URL.startswith("sqlite") else {},
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _seed_defaults()


def _seed_defaults():
    """Seed the single-row Settings table with economics defaults from env."""
    from . import models

    with SessionLocal() as db:
        s = db.get(models.Settings, 1)
        if s is None:
            s = models.Settings(
                id=1,
                mpg=config.DEFAULT_MPG,
                fixed_monthly_cents=config.FIXED_MONTHLY_CENTS,
                avg_monthly_miles=config.AVG_MONTHLY_MILES,
                maint_cpm_cents=config.MAINT_CPM_CENTS,
                target_margin_pct=config.TARGET_MARGIN_PCT,
            )
            db.add(s)
            db.commit()
