import io
import pypdf

def extract_text(raw: bytes, content_type: str) -> str:
    """Extract plain text from a PDF or txt file."""
    if content_type == "text/plain":
        return raw.decode("utf-8", errors="ignore")
    
    if content_type == "application/pdf":
        reader = pypdf.PdfReader(io.BytesIO(raw))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n\n" .join(pages)
    
    return ""