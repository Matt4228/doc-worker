import io
import pypdf

def extract_pages(raw: bytes, content_type: str) -> list[str]:
    """Extract text one page at a time, so answers can cite page numbers.

    A PDF gives one string per page, in order. A .txt file has no pages, so
    it comes back as a single entry. Anything else gives an empty list.
    """
    if content_type == "text/plain":
        return [raw.decode("utf-8", errors="ignore")]

    if content_type == "application/pdf":
        reader = pypdf.PdfReader(io.BytesIO(raw))
        return [page.extract_text() or "" for page in reader.pages]

    return []

def extract_text(raw: bytes, content_type: str) -> str:
    """Extract plain text from a PDF or txt file."""
    return "\n\n".join(extract_pages(raw, content_type))
