import json
import os
from typing import Literal
import anthropic
from fastapi import APIRouter, HTTPException
from models import ChatMessage, ChatRequest, ChatResponse
from services.anthropic import ask_question, retrieval_context, whole_context
from services.citations import cite_retrieval, cite_whole, strip_citations
from services.embeddings import EmbeddingBusy, EmbeddingError
from services.retrieval import retrieve
from db import get_pool
import uuid

router = APIRouter()

# How much of the stored conversation goes back to the model with each
# question. Older turns are dropped so a long chat can't grow the prompt (and
# the bill) without limit. Even, so the slice starts on a user turn.
HISTORY_MESSAGES = 20

# Documents up to this many characters are sent whole: cheap enough, and the
# model sees everything. Longer ones use retrieval. A starting point that the
# eval checks; set WHOLE_DOC_MAX_CHARS to change it without a deploy.
WHOLE_DOC_MAX_CHARS = int(os.environ.get("WHOLE_DOC_MAX_CHARS", "60000"))

BUSY = "The AI service is busy. Try again in a minute."
FAILED = "The AI service couldn't answer. Try again."

def choose_mode(content: str, has_chunks: bool) -> Literal["whole", "retrieval"]:
    """Retrieval only for long documents that have been indexed. Documents
    uploaded before retrieval existed have no chunks until the backfill
    runs, so they keep working in whole mode."""
    if has_chunks and len(content) > WHOLE_DOC_MAX_CHARS:
        return "retrieval"
    return "whole"

def retrieval_query(question: str, history: list[ChatMessage]) -> str:
    """A follow-up like "how do I undo it?" means nothing on its own, so the
    search also uses the previous question."""
    previous = next((m.content for m in reversed(history) if m.role == "user"), None)
    return f"{previous}\n{question}" if previous else question

@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Ask a question about a specific document."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT content, pages, EXISTS (SELECT 1 FROM chunks WHERE document_id = $1) AS has_chunks "
            "FROM documents WHERE id = $1",
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
    history = [ChatMessage(role=r["role"], content=strip_citations(r["content"])) for r in reversed(rows)]
    mode = choose_mode(row["content"], row["has_chunks"])

    # 429 and 529 are temporary, so the visitor is told to retry. Anything
    # else from the API is our problem, not theirs: a 502, not a raw 500.
    # Voyage errors get the same treatment: to the visitor it's one service.
    try:
        if mode == "retrieval":
            async with pool.acquire() as conn:
                chunks = await retrieve(conn, request.document_id, retrieval_query(request.message, history))
            context = retrieval_context(chunks)
        else:
            context = whole_context(row["pages"], row["content"])
        result = await ask_question(context=context, message=request.message, history=history, mode=mode)
    except (anthropic.RateLimitError, anthropic.OverloadedError, EmbeddingBusy):
        raise HTTPException(status_code=503, detail=BUSY)
    except (anthropic.APIError, EmbeddingError):
        raise HTTPException(status_code=502, detail=FAILED)

    if mode == "retrieval":
        answer, sources = cite_retrieval(result.text, chunks)
    else:
        answer, sources = cite_whole(result.text, len(row["pages"]) if row["pages"] else None)

    # Persist with the exchange. The sources go with the answer, so a
    # reloaded chat still shows its citations.
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO messages (document_id, role, content) VALUES ($1, $2, $3)",
            request.document_id, "user", request.message,
        )
        await conn.execute(
            "INSERT INTO messages (document_id, role, content, sources) VALUES ($1, $2, $3, $4::jsonb)",
            request.document_id, "assistant", answer, json.dumps([s.model_dump() for s in sources]),
        )

    return ChatResponse(answer=answer, document_id=str(request.document_id), sources=sources, mode=mode)

@router.get("/{document_id}/history")
async def get_history(document_id: uuid.UUID):
    """Retrieve the full chat history for a document."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT role, content, sources FROM messages WHERE document_id = $1 ORDER BY created_at ASC",
            document_id,
        )
    # asyncpg returns jsonb as a string. User messages, and answers saved
    # before sources existed, have none.
    return [
        {"role": r["role"], "content": r["content"], "sources": json.loads(r["sources"]) if r["sources"] else []}
        for r in rows
    ]
