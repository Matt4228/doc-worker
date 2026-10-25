import asyncio
import json

import httpx
import pytest

from services import embeddings


@pytest.fixture
def voyage(monkeypatch):
    """Route the embeddings client through a fake Voyage API. Each request
    is recorded; set state["status"] to make the API return an error."""
    monkeypatch.setenv("VOYAGE_API_KEY", "test-voyage-key")
    state = {"requests": [], "status": 200}

    def handler(request):
        body = json.loads(request.content)
        state["requests"].append(body)
        if state["status"] != 200:
            return httpx.Response(state["status"], json={"detail": "nope"})
        # Out of order on purpose: the client must sort by index.
        data = [{"index": i, "embedding": [float(len(text))] * embeddings.EMBED_DIM} for i, text in enumerate(body["input"])]
        return httpx.Response(200, json={"data": list(reversed(data)), "usage": {"total_tokens": 1}})

    monkeypatch.setattr(embeddings, "_transport", httpx.MockTransport(handler))
    return state


def test_documents_are_sent_with_the_document_input_type(voyage):
    asyncio.run(embeddings.embed_documents(["a", "bb"]))
    assert voyage["requests"][0]["model"] == embeddings.EMBED_MODEL
    assert voyage["requests"][0]["input_type"] == "document"


def test_query_uses_the_query_input_type(voyage):
    vector = asyncio.run(embeddings.embed_query("question"))
    assert voyage["requests"][0]["input_type"] == "query"
    assert len(vector) == embeddings.EMBED_DIM


def test_vectors_come_back_in_input_order(voyage):
    vectors = asyncio.run(embeddings.embed_documents(["a", "bb", "ccc"]))
    assert [v[0] for v in vectors] == [1.0, 2.0, 3.0]


def test_large_inputs_are_split_into_batches(voyage):
    texts = [f"t{i}" for i in range(embeddings.EMBED_BATCH * 2 + 1)]
    vectors = asyncio.run(embeddings.embed_documents(texts))
    assert len(voyage["requests"]) == 3
    assert len(vectors) == len(texts)


def test_rate_limit_is_busy(voyage):
    voyage["status"] = 429
    with pytest.raises(embeddings.EmbeddingBusy):
        asyncio.run(embeddings.embed_query("q"))


def test_other_api_errors_are_embedding_errors(voyage):
    voyage["status"] = 400
    with pytest.raises(embeddings.EmbeddingError):
        asyncio.run(embeddings.embed_query("q"))


def test_missing_api_key_is_an_embedding_error(voyage, monkeypatch):
    monkeypatch.delenv("VOYAGE_API_KEY")
    with pytest.raises(embeddings.EmbeddingError):
        asyncio.run(embeddings.embed_query("q"))
    assert voyage["requests"] == []


def test_to_pgvector_formats_a_vector_literal():
    assert embeddings.to_pgvector([0.5, -1.0]) == "[0.5,-1.0]"
