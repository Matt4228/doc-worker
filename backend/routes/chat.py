import anthropic
from fastapi import APIRouter, HTTPException
from models import ChatMessage, ChatRequest, ChatResponse
from services.anthropic import ask_question, whole_context
from db import get_pool
import uuid

router = APIRouter()

# How much of the stored conversation goes back to the model with each
# question. Older turns are dropped so a long chat can't grow the prompt (and
# the bill) without limit. Even, so the slice starts on a user turn.
HISTORY_MESSAGES = 20

@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Ask a question about a specific document."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT content FROM documents WHERE id = $1",
            request.document_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Document not found.")

        # The conversation comes from the database, not the request, so a
        # client can't forge earlier turns or send a huge history. Newest
        # first so LIMIT keeps the latest turns, then reversed below.
        rows = await conn.fetch(
            "SELECT role, content FROM messages WHERE document_id = $1 "
            "ORDER BY created_at DESC LIMIT $2",
            request.document_id, HISTORY_MESSAGES,
        )
    history = [ChatMessage(role=r["role"], content=r["content"]) for r in reversed(rows)]

    # 429 and 529 are temporary, so the visitor is told to retry. Anything
    # else from the API is our problem, not theirs: a 502, not a raw 500.
    try:
        result = await ask_question(
            context=whole_context(None, row["content"]),
            message=request.message,
            history=history,
            mode="whole",
        )
    except (anthropic.RateLimitError, anthropic.OverloadedError):
        raise HTTPException(status_code=503, detail="The AI service is busy. Try again in a minute.")
    except anthropic.APIError:
        raise HTTPException(status_code=502, detail="The AI service couldn't answer. Try again.")

    # Persist with the exchange
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO messages (document_id, role, content) VALUES ($1, $2, $3)",
            request.document_id, "user", request.message,
        )
        await conn.execute(
            "INSERT INTO messages (document_id, role, content) VALUES ($1, $2, $3)",
            request.document_id, "assistant", result.text,
        )

    return ChatResponse(answer=result.text, document_id=str(request.document_id), mode="whole")

@router.get("/{document_id}/history")
async def get_history(document_id: uuid.UUID):
    """Retrieve the full chat history for a document."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT role, content FROM messages WHERE document_id = $1 ORDER BY created_at ASC",
            document_id,
        )
    return [{"role": r["role"], "content": r["content"]} for r in rows]
