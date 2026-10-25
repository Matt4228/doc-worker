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


class FakeConnection:
    """Records every query and returns whatever the test queued up, so route
    tests run without Postgres."""

    def __init__(self):
        self.queries = []
        self.fetchrow_result = None
        self.fetch_result = []

    async def fetchrow(self, query, *args):
        self.queries.append((query, args))
        return self.fetchrow_result

    async def fetch(self, query, *args):
        self.queries.append((query, args))
        return self.fetch_result

    async def execute(self, query, *args):
        self.queries.append((query, args))
        return "OK"

    async def executemany(self, query, rows):
        self.queries.append((query, list(rows)))

    def transaction(self):
        class Transaction:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

        return Transaction()


class FakePool:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        pool = self

        class Acquire:
            async def __aenter__(self):
                return pool.conn

            async def __aexit__(self, *exc):
                return False

        return Acquire()


@pytest.fixture
def fake_db(monkeypatch):
    """Point the documents and chat routes at a FakeConnection and return it."""
    from routes import chat, documents

    conn = FakeConnection()

    async def get_pool():
        return FakePool(conn)

    monkeypatch.setattr(documents, "get_pool", get_pool)
    monkeypatch.setattr(chat, "get_pool", get_pool)
    return conn


@pytest.fixture
def fake_embed(monkeypatch):
    """Replace the Voyage calls with fixed 1024-dim vectors and record what
    was sent. Set record["raises"] to an exception to make them fail."""
    from services import embeddings

    record = {"documents": [], "queries": []}

    def maybe_raise():
        if "raises" in record:
            raise record["raises"]

    async def embed_documents(texts):
        maybe_raise()
        record["documents"].append(list(texts))
        return [[0.0] * embeddings.EMBED_DIM for _ in texts]

    async def embed_query(text):
        maybe_raise()
        record["queries"].append(text)
        return [0.0] * embeddings.EMBED_DIM

    monkeypatch.setattr(embeddings, "embed_documents", embed_documents)
    monkeypatch.setattr(embeddings, "embed_query", embed_query)
    return record
