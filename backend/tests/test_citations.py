from services.citations import cite_retrieval, cite_whole, strip_citations
from services.retrieval import Retrieved

CHUNKS = [
    Retrieved(id=10, page=5, content="first passage"),
    Retrieved(id=11, page=9, content="second passage"),
    Retrieved(id=12, page=None, content="third passage"),
]


def test_valid_retrieval_markers_become_canonical():
    answer, sources = cite_retrieval("See [2].", CHUNKS)
    assert answer == "See [[2]]."
    assert len(sources) == 3
    assert (sources[1].id, sources[1].page, sources[1].text) == (11, 9, "second passage")


def test_out_of_range_marker_is_removed():
    assert cite_retrieval("Yes [9].", CHUNKS)[0] == "Yes."


def test_zero_is_not_a_valid_marker():
    assert cite_retrieval("Yes [0].", CHUNKS)[0] == "Yes."


def test_marker_lists_are_split():
    assert cite_retrieval("Both [1, 3].", CHUNKS)[0] == "Both [[1]][[3]]."


def test_a_list_keeps_only_its_valid_markers():
    assert cite_retrieval("Both [1, 7].", CHUNKS)[0] == "Both [[1]]."


def test_whole_mode_pages_become_sources():
    answer, sources = cite_whole("A [Page 4]. B [Page 2]. C [Page 4].", 10)
    assert answer == "A [[1]]. B [[2]]. C [[1]]."
    assert [s.page for s in sources] == [4, 2]
    assert all(s.id is None and s.text is None for s in sources)


def test_whole_mode_accepts_short_and_listed_forms():
    answer, sources = cite_whole("A [p. 3]. B [Page 1, 2].", 10)
    assert answer == "A [[1]]. B [[2]][[3]]."
    assert [s.page for s in sources] == [3, 1, 2]


def test_whole_mode_page_out_of_range_is_removed():
    assert cite_whole("X [Page 900].", 300) == ("X.", [])


def test_whole_mode_without_pages_has_no_chips():
    assert cite_whole("X [Page 1].", None) == ("X.", [])


def test_strip_citations():
    assert strip_citations("A [[1]] b [[2]].") == "A b."
