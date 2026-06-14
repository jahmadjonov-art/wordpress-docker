import os
import tempfile

import pytest

# Point the app at a throwaway SQLite DB + data dir BEFORE importing app modules.
_TMP = tempfile.mkdtemp(prefix="dispatch-test-")
os.environ["DATA_DIR"] = _TMP
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_TMP, 'test.db')}"


@pytest.fixture()
def db():
    from app.db import SessionLocal, init_db
    from app import models

    init_db()
    session = SessionLocal()
    # clean slate per test
    session.query(models.LoadOutcome).delete()
    session.query(models.LoadScore).delete()
    session.query(models.Load).delete()
    session.query(models.LaneStat).delete()
    session.query(models.Broker).delete()
    session.query(models.ReferenceRate).delete()
    session.commit()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def settings(db):
    from app import models
    return db.get(models.Settings, 1)
