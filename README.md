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

- Python 3.12
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
# fill in DATABASE_URL, ANTHROPIC_API_KEY, and DEMO_PASSWORD

uvicorn main:app --reload
```

Tables are created automatically on startup (`CREATE TABLE IF NOT EXISTS`) — there's no separate migration step.

Run the tests from `backend/`:

```bash
pip install -r requirements-dev.txt
pytest
```

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

Every `/documents` and `/chat` request needs `Authorization: Bearer <DEMO_PASSWORD>`, and a missing or wrong password gets a 401. The check is attached where the routers are included in `main.py`, so new routes under those prefixes are protected automatically. It also fails closed: if `DEMO_PASSWORD` isn't set, the API answers 503 instead of serving requests. `/health` stays open for the host's health check, and `GET /auth/check` lets the frontend verify a password before saving it.

| Method | Path | Description |
|---|---|---|
| POST | `/documents/upload` | Upload a PDF or `.txt` file |
| GET | `/documents/` | List uploaded documents |
| DELETE | `/documents/{id}` | Delete a document and its chat history |
| POST | `/chat/` | Ask a question about a document |
| GET | `/chat/{id}/history` | Get the full chat history for a document |

## Deployment

The live demo runs on free tiers: the FastAPI backend on [Render](https://render.com) (configured in `render.yaml`), the Next.js frontend on [Vercel](https://vercel.com), and Postgres on [Neon](https://neon.com). The backend and database are both in AWS us-east-1.

Because the backend URL is public and every chat request costs money, there are two guardrails: the demo password above, and a monthly spend limit on the Anthropic workspace that the deployed API key belongs to. The model defaults to Claude Haiku 5.5 (`ANTHROPIC_MODEL` to change it).

Things that are easy to get wrong:

- **`NEXT_PUBLIC_API_URL` is baked into the frontend at build time.** Next.js inlines `NEXT_PUBLIC_*` variables into the JavaScript bundle, so changing it in Vercel needs a redeploy to take effect. Everything in it is public, which is why the demo password is typed in by the visitor and never stored in a `NEXT_PUBLIC_` variable.
- **`ALLOWED_ORIGINS` on Render must exactly match the Vercel URL** (scheme included, no trailing path). Otherwise the browser blocks every request with a CORS error.
- **Remove `&channel_binding=require` from Neon's connection string.** asyncpg doesn't recognize that parameter and passes it to Postgres as a server setting, which rejects the connection. Keep `sslmode=require`.
- **The first request after the backend has been idle takes about a minute,** because Render's free tier sleeps after 15 minutes without traffic. The password screen says so while it waits.

To deploy your own copy: create a Neon project, then in Render choose New > Blueprint and pick this repo. Enter `DATABASE_URL`, `ANTHROPIC_API_KEY`, `DEMO_PASSWORD`, and (temporarily) `http://localhost:3000` for `ALLOWED_ORIGINS`. Import the repo into Vercel with Root Directory `frontend` and `NEXT_PUBLIC_API_URL` set to the Render URL, then update `ALLOWED_ORIGINS` on Render to the Vercel URL.
