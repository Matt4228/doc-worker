from services.chunker import Chunk, chunk_pages


def words(prefix, n):
    """n distinct words, e.g. a0 a1 a2, so a test can tell which page and
    position every word came from."""
    return " ".join(f"{prefix}{i}" for i in range(n))


def test_short_page_is_one_chunk():
    assert chunk_pages(["a b c"], paged=True) == [Chunk(index=0, page=1, content="a b c")]


def test_chunks_never_cross_pages():
    chunks = chunk_pages([words("a", 500), words("b", 500)], paged=True, chunk_words=350, overlap_words=50)
    assert [c.page for c in chunks] == [1, 1, 2, 2]
    for chunk in chunks:
        prefix = "a" if chunk.page == 1 else "b"
        assert all(word.startswith(prefix) for word in chunk.content.split())


def test_overlap_repeats_the_tail():
    chunks = chunk_pages([words("a", 500)], paged=True, chunk_words=350, overlap_words=50)
    assert chunks[0].content.split()[-50:] == chunks[1].content.split()[:50]


def test_last_chunk_reaches_the_end_of_the_page():
    chunks = chunk_pages([words("a", 500)], paged=True, chunk_words=350, overlap_words=50)
    assert chunks[-1].content.split()[-1] == "a499"


def test_no_chunk_is_only_overlap():
    # 350 words fit in one window exactly; a second window would hold nothing new.
    assert len(chunk_pages([words("a", 350)], paged=True, chunk_words=350, overlap_words=50)) == 1


def test_indexes_are_sequential_across_pages():
    chunks = chunk_pages([words("a", 500), words("b", 500)], paged=True, chunk_words=350, overlap_words=50)
    assert [c.index for c in chunks] == list(range(len(chunks)))


def test_blank_pages_are_skipped():
    assert chunk_pages(["", "  ", "x"], paged=True) == [Chunk(index=0, page=3, content="x")]


def test_unpaged_chunks_have_no_page():
    chunks = chunk_pages([words("a", 800)], paged=False, chunk_words=350, overlap_words=50)
    assert len(chunks) > 1
    assert all(c.page is None for c in chunks)
