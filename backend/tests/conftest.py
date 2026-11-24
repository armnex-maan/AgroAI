import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

import tempfile

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["MEDIA_ROOT"] = tempfile.mkdtemp(prefix="agroai-test-media-")
os.environ["YAMNET_ENABLED"] = "false"  # no TF / network in unit tests
os.environ["BIRDNET_ENABLED"] = "false"
os.environ["PERCH_ENABLED"] = "false"  # 413 MB model + iNaturalist calls: not in unit tests
os.environ["AI_PROVIDER"] = "none"  # never call a real LLM (or spend the user's key) from tests

from app.core import database  # noqa: E402
from app.core.database import Base  # noqa: E402
from app import models  # noqa: F401, E402

# StaticPool so every session hits the SAME in-memory database.
_engine = create_engine(
    "sqlite+pysqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestSession = sessionmaker(bind=_engine, autoflush=False, autocommit=False, expire_on_commit=False)
database.engine = _engine
database.SessionLocal = _TestSession

from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _create_schema():
    Base.metadata.create_all(_engine)
    yield
    Base.metadata.drop_all(_engine)


@pytest.fixture()
def db():
    s = _TestSession()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture()
def client():
    return TestClient(app)
