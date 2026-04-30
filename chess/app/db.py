import os
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from . import config

if config.DATABASE_URL.startswith("sqlite:////"):
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
    _seed_player()


def _seed_player():
    from . import models

    with SessionLocal() as db:
        player = db.get(models.Player, 1)
        if player is None:
            db.add(models.Player(id=1, name=config.PLAYER_NAME, elo=config.START_ELO))
            db.commit()
