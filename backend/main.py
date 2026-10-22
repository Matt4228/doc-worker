import os
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import documents, chat
from db import init_db
from auth import require_demo_password
from dotenv import load_dotenv
load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(
    title="Doc Worker API",
    description="LLM-powered document intelligence - upload a document, ask questions about it.",
    version="0.1.0",
    lifespan=lifespan,
)

def allowed_origins() -> list[str]:
    """Frontend origins allowed to call the API, from ALLOWED_ORIGINS
    (comma-separated). Defaults to the local Next.js dev server."""
    raw = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000")
    return [origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip()]

# No credentials: the password travels in the Authorization header, not a
# cookie, so the browser never needs to send cookies cross-site.
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

# Attached at the router level so every current and future route under
# /documents and /chat is protected without each one having to opt in.
protected = [Depends(require_demo_password)]

app.include_router(documents.router, prefix="/documents", tags=["documents"], dependencies=protected)
app.include_router(chat.router, prefix="/chat", tags=["chat"], dependencies=protected)

@app.get("/auth/check", dependencies=protected)
def auth_check():
    """Lets the frontend verify a password before saving it."""
    return {"ok": True}

@app.get("/health")
def health():
    return {"status": "ok", "service": "doc-worker-api"}