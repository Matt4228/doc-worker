"""Retrieval against a real Postgres with pgvector.

Skipped unless TEST_DATABASE_URL is set. CI runs a pgvector container for
it. Locally, point it at a throwaway database, never production: the test
creates the schema if needed, adds its own document and deletes it.
"""
import asyncio
import os

import asyncpg
import pytest

from db import SCHEMA_SQL
from services.chunker import Chunk
from services.indexing import store_chunks
from services.retrieval import search_embedding, search_keyword

pytestmark = pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set")

TEXTS = [
    "How to undo a rebase safely with the reflog",
    "Branching and merging basics for new users",
    "Configuring your editor and other settings",
]


def one_hot(position):
    vector = [0.0] * 1024
    vector[position] = 1.0
    return vector


def with_document(test):
    """Run test(conn, document_id) against a fresh document with three
    chunks on pages 1 to 3, then delete it."""
    async def run():
        conn = await asyncpg.connect(os.environ["TEST_DATABASE_URL"])
        try:
            await conn.execute(SCHEMA_SQL)
            document_id = await conn.fetchval(
                "INSERT INTO documents (filename, content) VALUES ('retrieval-test', 'x') RETURNING id"
            )
            try:
                chunks = [Chunk(index=i, page=i + 1, content=text) for i, text in enumerate(TEXTS)]
                await store_chunks(conn, document_id, chunks, [one_hot(i) for i in range(3)])
                await test(conn, document_id)
            finally:
                await conn.execute("DELETE FROM documents WHERE id = $1", document_id)
        finally:
            await conn.close()

    asyncio.run(run())


def test_embedding_search_ranks_the_nearest_chunk_first():
    async def test(conn, document_id):
        found = await search_embedding(conn, document_id, one_hot(1), 3)
        assert found[0].page == 2
        assert len(found) == 3

    with_document(test)


def test_keyword_search_matches_any_word():
    async def test(conn, document_id):
        # "undo" and "rebase" are both in chunk 1; "everything" is in none.
        found = await search_keyword(conn, document_id, "undo everything rebase", 3)
        assert [c.page for c in found] == [1]

    with_document(test)


def test_keyword_search_with_only_stopwords_returns_empty():
    async def test(conn, document_id):
        assert await search_keyword(conn, document_id, "what is the", 3) == []

    with_document(test)


def test_deleting_a_document_deletes_its_chunks():
    async def test(conn, document_id):
        await conn.execute("DELETE FROM documents WHERE id = $1", document_id)
        assert await conn.fetchval("SELECT count(*) FROM chunks WHERE document_id = $1", document_id) == 0

    with_document(test)
