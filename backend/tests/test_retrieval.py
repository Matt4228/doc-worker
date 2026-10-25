import asyncio

from services import retrieval
from services.retrieval import Retrieved, rrf
from tests.conftest import FakeConnection

DOC_ID = "00000000-0000-0000-0000-000000000005"


def chunk(id, page=1):
    return Retrieved(id=id, page=page, content=f"chunk {id}")


def test_rrf_rewards_chunks_found_by_both():
    # Chunk 2 is second in both lists; chunks 1 and 3 top only one list each.
    keyword = [chunk(1), chunk(2)]
    embedding = [chunk(3), chunk(2)]
    assert rrf([keyword, embedding], k=3)[0].id == 2


def test_rrf_dedupes_by_id():
    fused = rrf([[chunk(1), chunk(2)], [chunk(2), chunk(1)]], k=5)
    assert sorted(c.id for c in fused) == [1, 2]


def test_rrf_returns_at_most_k():
    assert len(rrf([[chunk(i) for i in range(10)]], k=3)) == 3


def test_retrieve_returns_chunks_in_page_order(monkeypatch, fake_embed):
    async def search_embedding(conn, document_id, query_vec, k):
        return [chunk(1, page=40), chunk(2, page=3), chunk(3, page=12)]

    monkeypatch.setattr(retrieval, "search_embedding", search_embedding)
    found = asyncio.run(retrieval.retrieve(FakeConnection(), DOC_ID, "question", method="embedding"))
    assert [c.page for c in found] == [3, 12, 40]
    assert fake_embed["queries"] == ["question"]


def test_keyword_method_makes_no_embedding_call(monkeypatch, fake_embed):
    async def search_keyword(conn, document_id, query, k):
        return [chunk(1)]

    monkeypatch.setattr(retrieval, "search_keyword", search_keyword)
    found = asyncio.run(retrieval.retrieve(FakeConnection(), DOC_ID, "question", method="keyword"))
    assert [c.id for c in found] == [1]
    assert fake_embed["queries"] == []


def test_hybrid_fuses_both_searches(monkeypatch, fake_embed):
    async def search_keyword(conn, document_id, query, k):
        return [chunk(1), chunk(2)]

    async def search_embedding(conn, document_id, query_vec, k):
        return [chunk(3), chunk(2)]

    monkeypatch.setattr(retrieval, "search_keyword", search_keyword)
    monkeypatch.setattr(retrieval, "search_embedding", search_embedding)
    found = asyncio.run(retrieval.retrieve(FakeConnection(), DOC_ID, "question", k=2, method="hybrid"))
    assert 2 in [c.id for c in found]


def test_keyword_search_with_no_words_returns_empty():
    conn = FakeConnection()
    assert asyncio.run(retrieval.search_keyword(conn, DOC_ID, "?!", 6)) == []
    assert conn.queries == []
