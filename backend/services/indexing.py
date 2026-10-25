from services import embeddings
from services.chunker import Chunk

async def embed_chunks(chunks: list[Chunk]) -> list[list[float]]:
    """Embed each chunk's text. Called before anything is written, so a
    Voyage failure leaves nothing half saved."""
    if not chunks:
        return []
    return await embeddings.embed_documents([chunk.content for chunk in chunks])

async def store_chunks(conn, document_id, chunks: list[Chunk], vectors: list[list[float]]) -> None:
    """Insert a document's chunks and their vectors in one round trip."""
    await conn.executemany(
        "INSERT INTO chunks (document_id, chunk_index, page, content, embedding) "
        "VALUES ($1, $2, $3, $4, $5::vector)",
        [
            (document_id, chunk.index, chunk.page, chunk.content, embeddings.to_pgvector(vector))
            for chunk, vector in zip(chunks, vectors)
        ],
    )
