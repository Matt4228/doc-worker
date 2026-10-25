import re
from dataclasses import dataclass
from typing import Literal

from services import embeddings

# How many chunks go into the prompt, and how they're found. Starting
# points: the eval measures the alternatives and sets the shipped values.
TOP_K = 6
Method = Literal["keyword", "embedding", "hybrid"]
RETRIEVAL_METHOD: Method = "embedding"

@dataclass(frozen=True)
class Retrieved:
    id: int
    page: int | None
    content: str

def _rows_to_chunks(rows) -> list[Retrieved]:
    return [Retrieved(id=r["id"], page=r["page"], content=r["content"]) for r in rows]

async def search_embedding(conn, document_id, query_vec: list[float], k: int) -> list[Retrieved]:
    """The k chunks whose meaning is closest to the question. <=> is
    pgvector's cosine distance, so smaller means more similar."""
    rows = await conn.fetch(
        "SELECT id, page, content FROM chunks WHERE document_id = $1 "
        "ORDER BY embedding <=> $2::vector LIMIT $3",
        document_id, embeddings.to_pgvector(query_vec), k,
    )
    return _rows_to_chunks(rows)

async def search_keyword(conn, document_id, query: str, k: int) -> list[Retrieved]:
    """The k chunks that best match the question's words.

    plainto_tsquery joins the words with & (AND), which almost nothing
    matches for a natural question, so the & become | (OR) and ts_rank
    puts chunks matching more of the words first.
    """
    if not re.search(r"\w", query):
        return []
    rows = await conn.fetch(
        "WITH q AS (SELECT replace(plainto_tsquery('english', $2)::text, '&', '|')::tsquery AS query) "
        "SELECT id, page, content FROM chunks, q "
        "WHERE document_id = $1 AND tsv @@ q.query "
        "ORDER BY ts_rank(tsv, q.query) DESC LIMIT $3",
        document_id, query, k,
    )
    return _rows_to_chunks(rows)

def rrf(rankings: list[list[Retrieved]], k: int, rrf_k: int = 60) -> list[Retrieved]:
    """Reciprocal rank fusion: merge ranked lists by giving each chunk
    1 / (rrf_k + rank) per list it appears in. A chunk ranked well by both
    searches beats one ranked first by only one of them."""
    scores: dict[int, float] = {}
    chunks: dict[int, Retrieved] = {}
    for ranking in rankings:
        for rank, chunk in enumerate(ranking, start=1):
            scores[chunk.id] = scores.get(chunk.id, 0.0) + 1 / (rrf_k + rank)
            chunks[chunk.id] = chunk
    best = sorted(scores, key=scores.get, reverse=True)[:k]
    return [chunks[id] for id in best]

async def retrieve(conn, document_id, query: str, k: int = TOP_K, method: Method = RETRIEVAL_METHOD) -> list[Retrieved]:
    """Find the k chunks most relevant to the question, returned in page
    order so the prompt and the sources list read like the document."""
    if method == "keyword":
        found = await search_keyword(conn, document_id, query, k)
    else:
        query_vec = await embeddings.embed_query(query)
        if method == "embedding":
            found = await search_embedding(conn, document_id, query_vec, k)
        else:
            # Each search contributes extra candidates, so fusion has
            # something to choose between.
            found = rrf([
                await search_keyword(conn, document_id, query, 2 * k),
                await search_embedding(conn, document_id, query_vec, 2 * k),
            ], k)
    return sorted(found, key=lambda c: (c.page or 0, c.id))
