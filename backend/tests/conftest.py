import os
import tempfile

# Configure an isolated SQLite DB and offline providers before app import.
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_tmp.name}")
os.environ.setdefault("PROVIDER_MODE", "fixture")

import pytest
from fastapi.testclient import TestClient

from app.db import Base, engine
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def _create_schema():
    Base.metadata.create_all(engine)
    yield


@pytest.fixture()
def client():
    return TestClient(app)
