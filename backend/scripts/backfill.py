"""Index documents uploaded before retrieval existed.

Run from backend/ with DATABASE_URL pointing at the database to fill:

    python -m scripts.backfill

Safe to run again: documents that already have chunks are skipped.
"""
import asyncio
import os
import sys
import asyncpg
from dotenv import load_dotenv
from db import SCHEMA_SQL
from services.chunker import chunk_pages
from services.embeddings import EmbeddingBusy, EmbeddingError
from services.indexing import embed_chunks, store_chunks
from services.parser import extract_pages

async def backfill_document(conn, row) -> str:
    """Index one document. Returns "pages" when its stored PDF was
    re-extracted page by page, "text" when only its text was kept (older
    PDFs and .txt files, which get sources but no page citations), or
    "skipped" when it already has chunks."""
    if row["has_chunks"]:
        return "skipped"

    if row["file"] is not None:
        pages, kind = extract_pages(bytes(row["file"]), "application/pdf"), "pages"
    else:
        pages, kind = [row["content"]], "text"

    chunks = chunk_pages(pages, paged=kind == "pages")
    vectors = await embed_chunks(chunks)
    async with conn.transaction():
        if kind == "pages":
            await conn.execute("UPDATE documents SET pages = $2 WHERE id = $1", row["id"], pages)
        await store_chunks(conn, row["id"], chunks, vectors)
    return kind

async def main() -> int:
    load_dotenv()
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    try:
        await conn.execute(SCHEMA_SQL)
        # Ids first, then one document at a time, so at most one stored PDF
        # (up to 10 MB) is in memory.
        ids = await conn.fetch(
            "SELECT id FROM documents d WHERE NOT EXISTS (SELECT 1 FROM chunks c WHERE c.document_id = d.id) "
            "ORDER BY created_at"
        )
        counts = {"pages": 0, "text": 0, "skipped": 0, "failed": 0}
        for (document_id,) in ids:
            row = await conn.fetchrow(
                "SELECT id, filename, content, file, "
                "EXISTS (SELECT 1 FROM chunks WHERE document_id = $1) AS has_chunks "
                "FROM documents WHERE id = $1",
                document_id,
            )
            try:
                result = await backfill_document(conn, row)
            except (EmbeddingBusy, EmbeddingError) as e:
                result = "failed"
                print(f"failed   {row['filename']}: {e}")
            else:
                print(f"{result:<8} {row['filename']}")
            counts[result] += 1
        print(", ".join(f"{n} {kind}" for kind, n in counts.items()))
        return 1 if counts["failed"] else 0
    finally:
        await conn.close()

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
