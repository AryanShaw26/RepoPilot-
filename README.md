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
