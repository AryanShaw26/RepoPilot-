# RepoPilot

RepoPilot is a FastAPI backend and React/Vite frontend for repository analysis.

## Requirements

- Python 3.11–3.13 (Python 3.13 is the Windows target)
- Node.js 20 or later
- PostgreSQL 14 or later; pgvector is optional for semantic search

## Run locally on Windows

From the repository root, install backend dependencies and migrate the database:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

In another PowerShell window:

```powershell
cd frontend
npm install
npm run dev
```

Configure `backend/.env` and `frontend/.env` from their `.env.example` files.
The backend's `DATABASE_URL` must identify the local PostgreSQL database; the app
normalizes supported PostgreSQL URL schemes to the asyncpg driver.

The backend supports Anthropic, OpenAI, and Gemini for LLM requests. Set
`LLM_PROVIDER`, `LLM_API_KEY`, and `LLM_MODEL` together. Embeddings support OpenAI
and Gemini through `EMBEDDING_PROVIDER`, `EMBEDDING_API_KEY`, and `EMBEDDING_MODEL`;
Gemini requests the configured `EMBEDDING_DIM` output size. Gemini LLM responses
are requested as JSON and still pass schema validation with one repair attempt.
Transient provider responses (429/5xx) receive at most two retries; other HTTP
errors fail immediately. Semantic search makes no embedding requests when pgvector
is unavailable.

## Validation

From the repository root:

```powershell
cd backend
python -m pytest tests -q
python scripts/check_env.py
cd ..\frontend
npm run test
npm run build
```
