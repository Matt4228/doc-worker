from fastapi import APIRouter, HTTPException
from models import ChatRequest, ChatResponse
from services.anthropic import ask_question
from db import get_pool
import uuid

router = APIRouter()

@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Ask a question about a specific document."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT content FROM documents WHERE id = $1",
            uuid.UUID(request.document_id),
        )

    if not row:
        raise HTTPException(status_code=404, detail="Document not found.")
    
    answer = await ask_question(
        document_content=row["content"],
        message=request.message,
        history=request.history,
    )

    # Persist with the exchange
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO messages (document_id, role, content) VALUES ($1, $2, $3)",
            uuid.UUID(request.document_id), "user", request.message,
        )
        await conn.execute(
            "INSERT INTO messages (document_id, role, content) VALUES ($1, $2, $3)",
            uuid.UUID(request.document_id), "assistant", answer,
        )

    return ChatResponse(answer=answer, document_id=request.document_id)

@router.get("/{document_id}/history")
async def get_history(document_id: str):
    """Retrieve the full chat history for a document."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT role, content FROM messages WHERE document_id = $1 ORDER BY created_at ASC",
            uuid.UUID(document_id),
        )
    return [{"role": r["role"], "content": r["content"]} for r in rows]