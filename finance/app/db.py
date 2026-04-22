import os
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from . import config

os.makedirs(config.DATA_DIR, exist_ok=True)
os.makedirs(config.RAW_HTML_DIR, exist_ok=True)

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
    from . import models
    import json

    with SessionLocal() as db:
        goal = db.get(models.SavingsGoal, 1)
        if goal is None:
            buckets = [
                {"name": b["name"], "target_cents": b["target"] * 100, "current_cents": 0}
                for b in config.DEFAULT_BUCKETS
            ]
            total = sum(b["target_cents"] for b in buckets)
            goal = models.SavingsGoal(
                id=1,
                target_cents=total,
                buckets_json=json.dumps(buckets),
                weekly_save_cents=0,
            )
            db.add(goal)
            db.commit()
