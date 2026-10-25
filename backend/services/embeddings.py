import os
import httpx

# Voyage AI turns text into vectors. Anthropic has no embeddings API of its
# own and its docs point to Voyage. Called over plain HTTP: the official SDK
# would pull in LangChain's text splitters, a tokenizer and numpy for what is
# one POST request.
VOYAGE_URL = "https://api.voyageai.com/v1/embeddings"
EMBED_MODEL = "voyage-4"
EMBED_DIM = 1024  # must match vector(1024) in db.py

# Texts per request. A 350-word schunk is about 500 tokens, so a batch stays
# well under Voyage's per-request token limit.
EMBED_BATCH = 128

# Tests swap in an httpx.MockTransport so no request leaves the machine.
_transport: httpx.AsyncBaseTransport | None = None

class EmbeddingBusy(Exception):
    """Voyage is rate limiting or overloaded. Worth retrying in a minute."""

class EmbeddingError(Exception):
    """Any other embedding failure: bad key, bad request, network error."""

async def _embed(texts: list[str], input_type: str) -> list[list[float]]:
    key = os.environ.get("VOYAGE_API_KEY")
    if not key:
        raise EmbeddingError("VOYAGE_API_KEY is not set")

    vectors: list[list[float]] = []
    async with httpx.AsyncClient(transport=_transport, timeout=60) as client:
        for start in range(0, len(texts), EMBED_BATCH):
            batch = texts[start:start + EMBED_BATCH]
            try:
                response = await client.post(
                    VOYAGE_URL,
                    headers={"Authorization": f"Bearer {key}"},
                    json={"input": batch, "model": EMBED_MODEL, "input_type": input_type},
                )
            except httpx.HTTPError as e:
                raise EmbeddingError(str(e)) from e
            if response.status_code in (429, 503):
                raise EmbeddingBusy(response.text)
            if response.status_code != 200:
                raise EmbeddingError(f"Voyage returned {response.status_code}: {response.text}")
            # Each result carries the index of its input, so sort by it
            # rather than trusting the order they arrive in.
            data = sorted(response.json()["data"], key=lambda item: item["index"])
            vectors.extend(item["embedding"] for item in data)
    return vectors

async def embed_documents(texts: list[str]) -> list[list[float]]:
    """Embed chunks for storage. Voyage tunes vectors differently for the
    text being searched and for the question, hence the input_type."""
    return await _embed(texts, "document")

async def embed_query(text: str) -> list[float]:
    """Embed a question to compare against stored chunks."""
    return (await _embed([text], "query"))[0]

def to_pgvector(vector: list[float]) -> str:
    """Format a vector as pgvector's text form, e.g. "[0.1,0.2]", to pass
    as a query parameter cast with ::vector."""
    return "[" + ",".join(str(x) for x in vector) + "]"
