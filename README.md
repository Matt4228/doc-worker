# Doc Worker

LLM-powered document intelligence. Upload a PDF or text file, then ask natural-language questions about it in a chat interface backed by Claude.

## How it works

1. Upload a PDF or `.txt` file through the frontend.
2. The backend extracts its text (`pypdf` for PDFs) and stores it in Postgres.
3. Opening a document's chat view sends each question, plus the full document text and conversation history, to Claude via the Anthropic API.
4. Both sides of the exchange are persisted so history survives a page reload.

## Stack

- **Backend:** Python, FastAPI, asyncpg (raw SQL, no ORM), pypdf, Anthropic API
- **Frontend:** Next.js (App Router), React, TypeScript, Tailwind CSS
- **Database:** PostgreSQL

## Project layout

```
backend/    FastAPI app — routes, services, DB access
frontend/   Next.js app — upload UI, document list, chat window
```

## Local development

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL running locally (or reachable via `DATABASE_URL`)
- An Anthropic API key

### Backend

```bash
cd backend
python -m venv venv
./venv/Scripts/activate   # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt

createdb docworker        # or create the database however you prefer

cp .env.example .env
# fill in DATABASE_URL and ANTHROPIC_API_KEY

uvicorn main:app --reload
```

Tables are created automatically on startup (`CREATE TABLE IF NOT EXISTS`) — there's no separate migration step.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
# fill in NEXT_PUBLIC_API_URL if the backend isn't at http://localhost:8000

npm run dev
```

Then open http://localhost:3000.

## API

| Method | Path | Description |
|---|---|---|
| POST | `/documents/upload` | Upload a PDF or `.txt` file |
| GET | `/documents/` | List uploaded documents |
| DELETE | `/documents/{id}` | Delete a document and its chat history |
| POST | `/chat/` | Ask a question about a document |
| GET | `/chat/{id}/history` | Get the full chat history for a document |
