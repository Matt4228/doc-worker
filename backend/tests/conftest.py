import os

# services/anthropic.py builds its client at import time and reads this
# variable to do it. A placeholder is enough: no test calls the real API.
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-not-real")

import pytest
from fastapi.testclient import TestClient

PASSWORD = "correct horse battery staple"


@pytest.fixture
def client(monkeypatch):
    """A TestClient for the real app with DEMO_PASSWORD set.

    Deliberately not used as a context manager, so the lifespan hook (which
    connects to Postgres) never runs. Routes that would reach the database
    are either rejected by auth first or have their pool faked per test.
    """
    monkeypatch.setenv("DEMO_PASSWORD", PASSWORD)
    from main import app

    return TestClient(app)


@pytest.fixture
def auth_header():
    return {"Authorization": f"Bearer {PASSWORD}"}
