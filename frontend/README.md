# Doc Worker — Frontend

Next.js frontend for Doc Worker. See the [root README](../README.md) for the full project overview and setup (this app depends on the FastAPI backend in `../backend`).

## Development

```bash
npm install
cp .env.example .env.local
npm run dev
```

Runs on http://localhost:3000 and expects the backend at the URL set in `NEXT_PUBLIC_API_URL`.
