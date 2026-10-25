import asyncio

from services.chunker import Chunk
from services.indexing import embed_chunks, store_chunks
from tests.conftest import FakeConnection

DOC_ID = "00000000-0000-0000-0000-000000000004"


def test_store_chunks_inserts_every_chunk_in_one_executemany():
    conn = FakeConnection()
    chunks = [Chunk(0, 1, "first"), Chunk(1, 2, "second")]
    asyncio.run(store_chunks(conn, DOC_ID, chunks, [[0.5], [1.5]]))
    assert len(conn.queries) == 1
    query, rows = conn.queries[0]
    assert "INSERT INTO chunks" in query and "::vector" in query
    assert rows == [(DOC_ID, 0, 1, "first", "[0.5]"), (DOC_ID, 1, 2, "second", "[1.5]")]


def test_embed_chunks_sends_the_chunk_text(fake_embed):
    vectors = asyncio.run(embed_chunks([Chunk(0, 1, "first"), Chunk(1, 1, "second")]))
    assert fake_embed["documents"] == [["first", "second"]]
    assert len(vectors) == 2


def test_embed_chunks_with_nothing_to_embed_makes_no_call(fake_embed):
    assert asyncio.run(embed_chunks([])) == []
    assert fake_embed["documents"] == []
