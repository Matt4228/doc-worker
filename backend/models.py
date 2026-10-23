from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
import uuid

# Long enough for any real question, short enough that one request can't
# carry a pasted book. The chat box enforces the same limit.
MAX_MESSAGE_CHARS = 4000

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

# No history field: the server reads the conversation from the database.
# Older clients that still send one have it ignored.
class ChatRequest(BaseModel):
    document_id: uuid.UUID
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)

class ChatResponse(BaseModel):
    answer: str
    document_id: str