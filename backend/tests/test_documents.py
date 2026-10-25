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


def test_pdf_upload_stores_the_original_bytes_and_pages(client, auth_header, fake_db, fake_embed, monkeypatch):
    from routes import documents

    monkeypatch.setattr(documents, "extract_pages", lambda raw, content_type: ["page one", "page two"])
    fake_db.fetchrow_result = row()
    response = client.post(
        "/documents/upload",
        headers=auth_header,
        files={"file": ("report.pdf", PDF_BYTES, "application/pdf")},
    )
    assert response.status_code == 200
    _, args = fake_db.queries[0]
    assert args == ("report.pdf", "page one\n\npage two", "application/pdf", PDF_BYTES, ["page one", "page two"])


def test_text_upload_stores_no_file(client, auth_header, fake_db, fake_embed):
    fake_db.fetchrow_result = row(filename="notes.txt")
    response = client.post(
        "/documents/upload",
        headers=auth_header,
        files={"file": ("notes.txt", b"plain notes", "text/plain")},
    )
    assert response.status_code == 200
    _, args = fake_db.queries[0]
    # A text file has no pages, so it stores none and gets no page citations.
    assert args == ("notes.txt", "plain notes", "text/plain", None, None)


def upload_txt(client, auth_header, text=b"plain notes"):
    return client.post(
        "/documents/upload",
        headers=auth_header,
        files={"file": ("notes.txt", text, "text/plain")},
    )


def test_upload_indexes_the_document(client, auth_header, fake_db, fake_embed):
    fake_db.fetchrow_result = row(filename="notes.txt")
    response = upload_txt(client, auth_header)
    assert response.status_code == 200
    assert fake_embed["documents"] == [["plain notes"]]
    query, rows = fake_db.queries[1]
    assert "INSERT INTO chunks" in query
    assert len(rows) == 1


def test_upload_embedding_busy_is_503_and_saves_nothing(client, auth_header, fake_db, fake_embed):
    from services.embeddings import EmbeddingBusy

    fake_embed["raises"] = EmbeddingBusy()
    response = upload_txt(client, auth_header)
    assert response.status_code == 503
    assert "busy" in response.json()["detail"]
    assert fake_db.queries == []


def test_upload_embedding_error_is_502_and_saves_nothing(client, auth_header, fake_db, fake_embed):
    from services.embeddings import EmbeddingError

    fake_embed["raises"] = EmbeddingError()
    response = upload_txt(client, auth_header)
    assert response.status_code == 502
    assert fake_db.queries == []
