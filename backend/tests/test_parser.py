from services.parser import extract_pages, extract_text
from tests.helpers import make_pdf


def test_extract_pages_returns_one_entry_per_pdf_page():
    pages = extract_pages(make_pdf(["first page", "second page", "third page"]), "application/pdf")
    assert len(pages) == 3
    assert "second page" in pages[1]


def test_extract_pages_text_file_is_one_page():
    assert extract_pages(b"hello", "text/plain") == ["hello"]


def test_extract_pages_unsupported_type_is_empty():
    assert extract_pages(b"data", "image/png") == []


def test_extract_text_is_pages_joined():
    pdf = make_pdf(["alpha", "beta"])
    assert extract_text(pdf, "application/pdf") == "\n\n".join(extract_pages(pdf, "application/pdf"))
