import re
from models import Source
from services.retrieval import Retrieved

# What the model writes. Retrieval mode: [2] or [1, 3], numbering the
# excerpts it was given. Whole mode: [Page 12], [p. 12] or [Page 1, 2].
# The leading whitespace is captured so a removed marker takes it along.
_RETRIEVAL_MARKER = re.compile(r"(\s*)\[(\d+(?:\s*,\s*\d+)*)\]")
_PAGE_MARKER = re.compile(r"(\s*)\[(?:page|p\.)\s*(\d+(?:\s*,\s*\d+)*)\]", re.IGNORECASE)

# What gets stored and sent to the frontend: [[n]] is the nth entry of the
# message's sources (1-based), so a chip can only ever point at a source
# the server checked.
_CANONICAL = re.compile(r"\s*\[\[\d+\]\]")

def _rewrite(pattern: re.Pattern, answer: str, to_canonical) -> str:
    """Replace each marker list with canonical markers for its valid
    numbers, or remove it (and the space before it) if none are valid."""
    def replace(match: re.Match) -> str:
        numbers = [int(n) for n in re.findall(r"\d+", match.group(2))]
        valid = [i for i in (to_canonical(n) for n in numbers) if i is not None]
        if not valid:
            return ""
        return match.group(1) + "".join(f"[[{i}]]" for i in valid)
    return pattern.sub(replace, answer)

def cite_retrieval(answer: str, chunks: list[Retrieved]) -> tuple[str, list[Source]]:
    """Every retrieved chunk becomes a source, in order, so the sources row
    shows all of them. Markers outside 1..len(chunks) are dropped."""
    sources = [Source(id=c.id, page=c.page, text=c.content) for c in chunks]
    answer = _rewrite(_RETRIEVAL_MARKER, answer, lambda n: n if 1 <= n <= len(chunks) else None)
    return answer, sources

def cite_whole(answer: str, page_count: int | None) -> tuple[str, list[Source]]:
    """Nothing was retrieved, so the only check possible is that a cited
    page exists. Each distinct page becomes a source, in order of first
    citation. Without stored pages, every page marker is dropped."""
    sources: list[Source] = []

    def to_canonical(page: int) -> int | None:
        if page_count is None or not 1 <= page <= page_count:
            return None
        for i, source in enumerate(sources, start=1):
            if source.page == page:
                return i
        sources.append(Source(id=None, page=page, text=None))
        return len(sources)

    answer = _rewrite(_PAGE_MARKER, answer, to_canonical)
    return answer, sources

def strip_citations(text: str) -> str:
    """Remove canonical markers from a stored answer before it goes back
    to the model as history: the numbers meant nothing outside that turn."""
    return _CANONICAL.sub("", text)
