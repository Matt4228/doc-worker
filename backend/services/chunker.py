from dataclasses import dataclass

# Sizes are in words, a close enough stand-in for tokens that the chunker
# needs no tokenizer. Starting points: the eval may tune them.
CHUNK_WORDS = 350
OVERLAP_WORDS = 50

@dataclass(frozen=True)
class Chunk:
    index: int        # 0-based position in the document
    page: int | None  # 1-based PDF page, None for .txt files
    content: str

def chunk_pages(
    pages: list[str],
    paged: bool,
    chunk_words: int = CHUNK_WORDS,
    overlap_words: int = OVERLAP_WORDS,
) -> list[Chunk]:
    """Split a document into overlapping chunks that never cross a page.

    Keeping each chunk on one page means every chunk has exactly one page
    number to cite. The overlap repeats the end of one chunk at the start of
    the next, so a sentence on a boundary is whole in at least one of them.
    """
    step = chunk_words - overlap_words
    chunks = []
    for page_number, text in enumerate(pages, start=1):
        words = text.split()
        start = 0
        while words:
            chunks.append(Chunk(
                index=len(chunks),
                page=page_number if paged else None,
                content=" ".join(words[start:start + chunk_words]),
            ))
            # Stop once a window reaches the end of the page, so the last
            # chunk is never just a repeat of the previous one's tail.
            if start + chunk_words >= len(words):
                break
            start += step
    return chunks
