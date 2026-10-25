from fastapi import APIRouter, UploadFile, File, HTTPException, Response
from services.parser import extract_pages
from db import get_pool
from models import DocumentDetail, DocumentSummary
import uuid

router = APIRouter()

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10MB, matches the frontend's stated limit
PDF_MAGIC = b"%PDF-"


async def _read_limited(file: UploadFile, limit: int) -> bytes:
    """Read an upload in chunks, aborting as soon as it exceeds `limit` bytes."""
    chunks = []
    total = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise HTTPException(status_code=413, detail="File exceeds the 10MB upload limit.")
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/upload", response_model=DocumentSummary)
async def upload_document(file: UploadFile = File(...)):
    """Upload a PDF or .txt file and store its extracted text."""
    if file.content_type not in ("application/pdf", "text/plain"):
        raise HTTPException(status_code=400, detail="Only PDF and .txt files are supported.")

    raw = await _read_limited(file, MAX_UPLOAD_BYTES)

    if file.content_type == "application/pdf" and not raw.startswith(PDF_MAGIC):
        raise HTTPException(status_code=400, detail="File does not appear to be a valid PDF.")

    try:
        pages = extract_pages(raw, file.content_type)
    except Exception:
        raise HTTPException(status_code=422, detail="Could not read this file.")

    content = "\n\n".join(pages)
    if not content.strip():
        raise HTTPException(status_code=422, detail="Could not extract text from this file.")
    
    # Keep the original PDF so the chat page can render it, and its per-page
    # text so answers can cite pages. A text file is fully represented by its
    # content and has no pages, so it stores neither.
    is_pdf = file.content_type == "application/pdf"
    original = raw if is_pdf else None

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO documents (filename, content, content_type, file, pages) VALUES ($1, $2, $3, $4, $5) "
            "RETURNING id, filename, created_at",
            file.filename,
            content,
            file.content_type,
            original,
            pages if is_pdf else None,
        )

    return DocumentSummary(id=str(row["id"]), filename=row["filename"], created_at=row["created_at"])

@router.get("/", response_model=list[DocumentSummary])
async def list_documents():
    """Return all uploaded documents."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT id, filename, created_at FROM documents ORDER BY created_at DESC")
    return [DocumentSummary(id=str(r["id"]), filename=r["filename"], created_at=r["created_at"]) for r in rows]

# document_id is typed uuid.UUID, so FastAPI answers a malformed id with a
# 422 instead of uuid.UUID() raising a 500 (see #4).
@router.get("/{document_id}", response_model=DocumentDetail)
async def get_document(document_id: uuid.UUID):
    """Return a document's metadata and extracted text (never the file bytes)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, filename, created_at, content_type, file IS NOT NULL AS has_file, content "
            "FROM documents WHERE id = $1",
            document_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Document not found.")
    return DocumentDetail(
        id=str(row["id"]),
        filename=row["filename"],
        created_at=row["created_at"],
        content_type=row["content_type"],
        has_file=row["has_file"],
        content=row["content"],
    )

@router.get("/{document_id}/file")
async def get_document_file(document_id: uuid.UUID):
    """Return the original PDF for the viewer."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT file FROM documents WHERE id = $1", document_id)
    if not row or row["file"] is None:
        raise HTTPException(status_code=404, detail="No stored file for this document.")
    return Response(
        content=bytes(row["file"]),
        media_type="application/pdf",
        # private: the response is behind the demo password, so shared caches
        # must not keep it. An uploaded document never changes, so the
        # browser can reuse it for a day.
        headers={"Cache-Control": "private, max-age=86400"},
    )

@router.delete("/{document_id}")
async def delete_document(document_id: uuid.UUID):
    """Delete a document and its associated chat history."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM documents WHERE id = $1", document_id)
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Document not found.")
    return {"deleted": str(document_id)}