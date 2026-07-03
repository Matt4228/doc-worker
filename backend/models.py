from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class Document(BaseModel):
    id: str
    filename: str
    content: str
    created_at: datetime

class DocumentSummary(BaseModel):
    id: str
    filename: str
    created_at: datetime

class ChatMessage(BaseModel):
    role: str # "user" or "assistant"
    content: str

class ChatRequest(BaseModel):
    document_id: str
    message: str
    history: list[ChatMessage] = []

class ChatResponse(BaseModel):
    answer: str
    document_id: str