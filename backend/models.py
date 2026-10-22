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

class DocumentDetail(DocumentSummary):
    content_type: Optional[str]
    has_file: bool  # whether the original PDF is stored and can be rendered
    content: str  # extracted text, shown when there's no file to render

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