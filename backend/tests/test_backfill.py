import asyncio

from scripts.backfill import backfill_document
from tests.conftest import FakeConnection
from tests.helpers import make_pdf

DOC_ID = "00000000-0000-0000-0000-000000000006"


def row(**overrides):
    values = {"id": DOC_ID, "filename": "old.pdf", "content": "old text", "file": None, "has_chunks": False}
    return {**values, **overrides}


def test_backfill_reextracts_pages_from_stored_pdf(fake_embed):
    conn = FakeConnection()
    result = asyncio.run(backfill_document(conn, row(file=make_pdf(["page one", "page two"]))))
    assert result == "pages"
    update = next(args for query, args in conn.queries if query.startswith("UPDATE documents SET pages"))
    assert len(update[1]) == 2
    _, chunk_rows = next((q, a) for q, a in conn.queries if "INSERT INTO chunks" in q)
    assert [r[2] for r in chunk_rows] == [1, 2]


def test_backfill_chunks_text_only_rows_without_pages(fake_embed):
    conn = FakeConnection()
    result = asyncio.run(backfill_document(conn, row(content="plain words from an old upload")))
    assert result == "text"
    assert not any(query.startswith("UPDATE") for query, _ in conn.queries)
    _, chunk_rows = next((q, a) for q, a in conn.queries if "INSERT INTO chunks" in q)
    assert all(r[2] is None for r in chunk_rows)


def test_backfill_skips_indexed_documents(fake_embed):
    conn = FakeConnection()
    assert asyncio.run(backfill_document(conn, row(has_chunks=True))) == "skipped"
    assert conn.queries == []
    assert fake_embed["documents"] == []
