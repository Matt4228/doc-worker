from fastapi import APIRouter, UploadFile, File, HTTPException
from services.parser import extract_text
from db import get_pool
from models import DocumentSummary
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
        content = extract_text(raw, file.content_type)
    except Exception:
        raise HTTPException(status_code=422, detail="Could not read this file.")

    if not content.strip():
        raise HTTPException(status_code=422, detail="Could not extract text from this file.")
    
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO documents (filename, content) VALUES ($1, $2) RETURNING id, filename, created_at",
            file.filename,
            content,
        )

    return DocumentSummary(id=str(row["id"]), filename=row["filename"], created_at=row["created_at"])

@router.get("/", response_model=list[DocumentSummary])
async def list_documents():
    """Return all uploaded documents."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT id, filename, created_at FROM documents ORDER BY created_at DESC")
    return [DocumentSummary(id=str(r["id"]), filename=r["filename"], created_at=r["created_at"]) for r in rows]

@router.delete("/{document_id}")
async def delete_document(document_id: str):
    """Delete a document and its associated chat history."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM documents WHERE id = $1", uuid.UUID(document_id))
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Document not found.")
    return {"deleted": document_id}