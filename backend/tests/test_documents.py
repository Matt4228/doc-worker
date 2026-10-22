from datetime import datetime, timezone

DOC_ID = "00000000-0000-0000-0000-000000000002"
CREATED = datetime(2026, 10, 22, tzinfo=timezone.utc)
PDF_BYTES = b"%PDF-1.4 fake pdf body"


def row(**overrides):
    values = {
        "id": DOC_ID,
        "filename": "report.pdf",
        "created_at": CREATED,
        "content_type": "application/pdf",
        "has_file": True,
        "content": "Extracted text",
    }
    return {**values, **overrides}


def test_get_document_returns_metadata_and_text(client, auth_header, fake_db):
    fake_db.fetchrow_result = row()
    response = client.get(f"/documents/{DOC_ID}", headers=auth_header)
    assert response.status_code == 200
    body = response.json()
    assert body["filename"] == "report.pdf"
    assert body["has_file"] is True
    assert body["content"] == "Extracted text"


def test_get_document_never_selects_the_file_bytes(client, auth_header, fake_db):
    # The detail view only needs to know a file exists. Pulling a 10 MB
    # bytea column into memory on every page load would be wasteful.
    fake_db.fetchrow_result = row()
    client.get(f"/documents/{DOC_ID}", headers=auth_header)
    query, _ = fake_db.queries[0]
    assert "file IS NOT NULL AS has_file" in query
    assert ", file," not in query and "SELECT file" not in query


def test_get_missing_document_is_404(client, auth_header, fake_db):
    fake_db.fetchrow_result = None
    response = client.get(f"/documents/{DOC_ID}", headers=auth_header)
    assert response.status_code == 404


def test_malformed_document_id_is_422_not_500(client, auth_header, fake_db):
    response = client.get("/documents/not-a-uuid", headers=auth_header)
    assert response.status_code == 422
    assert fake_db.queries == []


def test_get_file_returns_the_pdf(client, auth_header, fake_db):
    fake_db.fetchrow_result = {"file": PDF_BYTES}
    response = client.get(f"/documents/{DOC_ID}/file", headers=auth_header)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["cache-control"].startswith("private")
    assert response.content == PDF_BYTES


def test_get_file_is_404_when_none_was_stored(client, auth_header, fake_db):
    # Text uploads, and PDFs uploaded before files were kept.
    fake_db.fetchrow_result = {"file": None}
    response = client.get(f"/documents/{DOC_ID}/file", headers=auth_header)
    assert response.status_code == 404


def test_pdf_upload_stores_the_original_bytes(client, auth_header, fake_db, monkeypatch):
    from routes import documents

    monkeypatch.setattr(documents, "extract_text", lambda raw, content_type: "text from pdf")
    fake_db.fetchrow_result = row()
    response = client.post(
        "/documents/upload",
        headers=auth_header,
        files={"file": ("report.pdf", PDF_BYTES, "application/pdf")},
    )
    assert response.status_code == 200
    _, args = fake_db.queries[0]
    assert args == ("report.pdf", "text from pdf", "application/pdf", PDF_BYTES)


def test_text_upload_stores_no_file(client, auth_header, fake_db):
    fake_db.fetchrow_result = row(filename="notes.txt")
    response = client.post(
        "/documents/upload",
        headers=auth_header,
        files={"file": ("notes.txt", b"plain notes", "text/plain")},
    )
    assert response.status_code == 200
    _, args = fake_db.queries[0]
    assert args == ("notes.txt", "plain notes", "text/plain", None)
