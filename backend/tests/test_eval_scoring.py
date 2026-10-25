import pytest

from eval.scoring import citation_accuracy, cited_pages, cost, hit, parse_verdict
from models import Source


def test_hit_when_any_expected_page_was_retrieved():
    assert hit([3, 12, 40], [12, 13]) is True


def test_miss_when_no_expected_page_was_retrieved():
    assert hit([3, 40], [12]) is False


def test_hit_is_none_for_unanswerable_questions():
    assert hit([3, 40], []) is None


def test_cited_pages_follow_the_markers_in_the_answer():
    sources = [Source(id=1, page=5, text="a"), Source(id=2, page=9, text="b"), Source(id=3, page=None, text="c")]
    # Source 2 was retrieved but not cited; source 3 has no page. Each
    # citation counts, so page 5 appears twice.
    assert cited_pages("See [[1]] and [[3]], again [[1]].", sources) == [5, 5]


def test_citation_accuracy_is_the_share_of_cited_pages_expected():
    assert citation_accuracy([22, 22, 40], [22]) == 2 / 3


def test_citation_accuracy_is_none_without_citations_or_for_unanswerable():
    assert citation_accuracy([], [22]) is None
    assert citation_accuracy([22], []) is None


def test_haiku_cost_switches_to_the_long_prompt_rate_above_100k():
    assert cost("claude-haiku-5-5", 100_000, 0) == pytest.approx(0.01)
    assert cost("claude-haiku-5-5", 200_000, 1_000_000) == pytest.approx(0.10 + 2.50)


def test_parse_verdict_reads_json_inside_text():
    assert parse_verdict('Sure. {"correct": true, "reason": "Matches."}') == (True, "Matches.")


def test_parse_verdict_without_json_is_unknown():
    assert parse_verdict("no idea") == (None, "Grader reply had no verdict: no idea")
