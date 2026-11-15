# RepoPilot — Fix & Verification Brief (`fixed_update.md`)

> **Audience:** the AI coding agent that built RepoPilot.
> **Read with:** `prd.md`, `design.md`, `implementation_guide.md`.
> **Goal:** fix the startup/database errors the owner hit on his own machine, verify the whole website works end to end, check the `.env` files, and send back a diagnostic report.

---

## 0. Ground Rules

1. **Never print, log, commit or include in the report any secret value** (`GITHUB_TOKEN`, `LLM_API_KEY`, `EMBEDDING_API_KEY`, DB password). Mask them as `****` and report only *whether* they are set. For `DATABASE_URL`, report scheme, host, port and database name only — never the password.
2. **Do not edit `backend/.env` or `frontend/.env`.** They belong to the owner. You may edit `.env.example` and the code. If a `.env` change is needed, tell the owner exactly what to change.
3. **Fix root causes in code**, not only in the owner's environment. The app must behave sensibly on a machine that differs from yours.
4. **Do not execute code from analysed repositories** and do not weaken any trust rule from `prd.md` §2 while fixing things.
5. Stay inside `prd.md` scope: no new features unless a section below asks for it.
6. Commit after each fix section: `fix: <short description>`.

---

## 1. The Owner's Environment (Where the Errors Came From)

| Item | Value |
|---|---|
| OS / shell | Windows, PowerShell |
| Python | 3.13 (venv at `backend\.venv`). *You tested on 3.10 — this difference matters.* |
| Database | Local PostgreSQL, user `postgres`, database `repopilot`, `localhost:5432`. **No Docker.** |
| Run commands | From `backend/`: `uvicorn app.main:app --reload` · From `frontend/`: `npm run dev` |
| Files present | `backend/.env` (exists, correctly named) and `backend/.env.example` |

### 1.1 Errors observed

**Error A — async driver crash at import time (blocking):**
```
backend\app\db\session.py, line 7: engine = create_async_engine(settings.DATABASE_URL, ..., connect_args={"timeout": 2.0})
sqlalchemy.exc.InvalidRequestError: The asyncio extension requires an async driver to be used. The loaded 'psycopg2' is not async.
```
Meaning: the `DATABASE_URL` that `settings` actually loaded has **no `+asyncpg` driver** (for example `postgresql://…` or `postgres://…`). The owner says the value in his `.env` is `postgresql+asyncpg://postgres:password@localhost:5432/repopilot`, so the app is **not reading the value he wrote**, or it is reading it incorrectly.

**Error B — settings import mismatch:**
```
ImportError: cannot import name 'settings' from 'app.core.config'
```
`db/session.py` uses `settings.DATABASE_URL`, but `app.core.config` does not export a module-level `settings` (it likely exposes `get_settings()`). Imports are inconsistent across modules.

**Error C — earlier run (already resolved, keep it from regressing):**
- `password authentication failed for user "repopilot"` → wrong credentials in `DATABASE_URL`.
- `relation "repositories" does not exist` → migrations had not been run. The cleanup task logged a long SQL error instead of degrading cleanly.

---

## 2. Fixes to Implement

### Fix 2.1 — One canonical settings object, loaded reliably

In `backend/app/core/config.py`:

1. Export both: `get_settings()` (cached) **and** a module-level `settings = get_settings()`, so every existing import style works. Then grep the whole backend (`app/`, `alembic/`, `tests/`) and make every module import it the same way.
2. Resolve the env file by **absolute path**, not by the current working directory:
   ```python
   from pathlib import Path
   BASE_DIR = Path(__file__).resolve().parents[2]   # .../backend
   model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", env_file_encoding="utf-8-sig", extra="ignore")
   ```
   `utf-8-sig` is intentional: Windows editors often save a BOM, which silently corrupts the first variable name.
3. Make `DATABASE_URL` **self-correcting** with a `field_validator("DATABASE_URL", mode="before")`:
   - strip whitespace and surrounding single/double quotes;
   - `postgres://…`, `postgresql://…`, `postgresql+psycopg2://…`, `postgresql+psycopg://…` → rewrite the scheme to `postgresql+asyncpg://`;
   - convert query param `sslmode=require` → `ssl=require` (asyncpg does not accept `sslmode`); drop `channel_binding` if present;
   - raise a clear `ValueError` if the scheme is not a PostgreSQL one.
4. Add a **masked startup log line**, e.g. `Database: driver=asyncpg host=localhost port=5432 db=repopilot user=postgres` (never the password).
5. Add `settings_diagnostics()` returning, per variable, `set` / `not set` / `default` and the **source** (`.env file`, `OS environment`, `default`) — values masked. Expose it only through the CLI script in Fix 2.6, **not** an HTTP endpoint.
6. Detect OS-environment overrides: if `DATABASE_URL` is set in the OS environment *and* in `backend/.env` with different values, log a warning at startup that the OS variable wins.

### Fix 2.2 — Database layer must not crash on import

In `backend/app/db/session.py`:
1. Build the engine lazily (factory/`get_engine()`), not at import time, so a bad URL produces a clear startup error instead of an import traceback.
2. `connect_args={"timeout": 2.0}` is too aggressive for a cold local Postgres on Windows — use `command_timeout=30` and a connect `timeout` of about 10 s. `pool_pre_ping=True`.
3. Keep `get_db` and the `async_sessionmaker` exports unchanged for the routers.

### Fix 2.3 — Alembic uses the same URL logic

In `backend/alembic/env.py`: import the same `settings`, use the normalised async URL, and run migrations with the async engine pattern from the `prd.md`/Phase 1 spec. Confirm `alembic upgrade head` works from `backend/` on Windows with the venv active. `alembic.ini` must not contain a hard-coded URL.

### Fix 2.4 — Graceful degradation instead of tracebacks

1. Startup (`lifespan`): check the DB with `SELECT 1`. If it fails, log **one** readable line (e.g. `Cannot connect to PostgreSQL at localhost:5432/repopilot — check DATABASE_URL and that the server is running`) and keep the app up in degraded mode.
2. Also check that the schema is migrated (`SELECT to_regclass('public.repositories')`). If it is missing, log: `Database is empty. Run: alembic upgrade head`. Do not run the cleanup task in that state.
3. Wrap the cleanup/retention loop so one failure logs a single warning (no full SQL dump) and the loop continues.
4. `GET /api/v1/health` must return `status`, `db` (bool), `migrated` (bool), `semantic_enabled`, `llm_configured` (bool), `github_token_configured` (bool), `version`. `status` is `ok` only if `db` and `migrated` are true; otherwise `degraded`.
5. API calls that need the DB, while it is unavailable, must return the standard error envelope with HTTP 503 and code `DATABASE_UNAVAILABLE` — not a 500 traceback. Add that code to `prd.md` §8 error list.

### Fix 2.5 — Python 3.13 compatibility

The owner runs Python 3.13; you validated on 3.10.
1. Run a full import smoke test under 3.13: `python -c "import app.main"` and `pytest backend/tests -q`.
2. Check that every pin in `requirements.txt` installs on 3.13 (asyncpg needs a recent version; **`tree-sitter-languages` has no 3.13 wheels** — if it fails or is missing, switch to the per-language packages `tree-sitter` + `tree-sitter-python`, `tree-sitter-javascript`, `tree-sitter-typescript`, `tree-sitter-java`, `tree-sitter-go`, adjusting `parser.py`).
3. If a language grammar cannot load, the parser must log once and skip that language (files still listed, symbols empty) — never fail the job.
4. Add `python_requires`/a note in `README.md`: supported versions 3.11–3.13, tested versions listed.
5. Windows specifics to verify: `asyncio.create_subprocess_exec` for `rg` works (the ProactorEventLoop is default); if `rg` is not installed, keyword search must fall back to Postgres FTS/trigram and say so (do not crash). Use `pathlib` everywhere; no hard-coded `/` path assumptions; normalise repo paths to `/` in API output.

### Fix 2.6 — Self-diagnosis script for the owner

Create `backend/scripts/check_env.py` (run with `python scripts/check_env.py` from `backend/`). It must:
1. Load settings through the same code path as the app.
2. For `backend/.env` and `frontend/.env` compare keys against the matching `.env.example`: list **missing**, **empty**, **unknown/duplicate** keys, a BOM, CRLF-vs-LF anomalies, surrounding quotes, and whether the file is git-ignored (`git check-ignore`).
3. Print masked results, e.g. `GITHUB_TOKEN: set (github_pat_****)`, `LLM_API_KEY: empty (AI features disabled)`.
4. Report the effective `DATABASE_URL` shape (driver/host/port/db) and whether an OS environment variable overrides the file.
5. Try a real DB connection (`SELECT 1`), check migrations (`to_regclass`), check `pg_extension` for `vector`, `pg_trgm`, `pgcrypto`, and print the next action in plain language for each failure.
6. Check `rg` (ripgrep) availability and the writability of `SNAPSHOT_DIR`.
7. Exit code 0 only if everything required passes. Never print a secret.

### Fix 2.7 — Frontend ↔ backend connectivity

1. `frontend/src/api/client.ts` reads `import.meta.env.VITE_API_BASE_URL`; if it is missing, fall back to `http://localhost:8000/api/v1` **and** log a console warning.
2. CORS: `FRONTEND_ORIGIN` may hold one or several comma-separated origins; also allow `http://127.0.0.1:5173` in development. Confirm `expose_headers=["X-Session-Id"]` and `allow_headers` include `X-Session-Id` and `Content-Type`. Verify the preflight (`OPTIONS`) responses.
3. The UI must show a clear banner when `/health` reports `db:false` or `migrated:false` (“Backend is running but the database isn’t ready”) rather than a blank or spinning page.

---

## 3. Authentication: What to Test

`prd.md` §1.5 and §10 define the MVP as **anonymous sessions** (no accounts): the browser stores a UUID from the `X-Session-Id` header, and every repository, investigation and plan is scoped to it.

- **If the codebase implements register/login:** test it fully (register → login → logout → protected route rejects unauthenticated access → session isolation between two users).
- **If it does not (expected):** **do not add login/registration on your own.** Test the anonymous session flow instead (Section 6, test group 3) and state clearly in the report that no register/login exists. The owner will decide whether to add accounts later.

---

## 4. Implementation Order

Do these in order. Re-run the gate after each step.

| Step | Work | Gate |
|---|---|---|
| 1 | Fix 2.1 (settings) and 2.2 (engine) | `python -c "import app.main"` succeeds; `python -c "from app.core.config import settings, get_settings; print(settings.DATABASE_URL.split('://')[0])"` prints `postgresql+asyncpg` (scheme only — never print the whole URL) |
| 2 | Fix 2.3 (Alembic) | With a local Postgres: `alembic upgrade head` → tables exist; running it twice is a no-op |
| 3 | Fix 2.4 (degradation + health) | Start with a **wrong password** → app starts, `/health` = degraded, one readable log line. Start with an **empty DB** → `migrated:false` message. Start normally → `status:"ok"` |
| 4 | Fix 2.5 (3.13 compat) | Fresh venv on Python 3.13: `pip install -r requirements.txt` and `pytest` pass; the parser test confirms symbols/imports for Python and JS/TS |
| 5 | Fix 2.6 (check script) | `python scripts/check_env.py` produces the masked report and correct exit code |
| 6 | Fix 2.7 (frontend/CORS) | Browser console shows no CORS errors; health banner appears when the DB is down |
| 7 | Regression tests | Add tests for: the DATABASE_URL validator (every scheme variant, quotes, `sslmode`), BOM/CRLF `.env` parsing, `/health` states, `DATABASE_UNAVAILABLE` envelope |

---

## 5. Environment and `.env` Checks (Run Before Testing)

1. Run `python backend/scripts/check_env.py` and include its (masked) output in the report.
2. Confirm both `.env.example` files exactly match the variable lists in `prd.md` §11; add anything missing and update `prd.md` if you added variables.
3. Confirm `git ls-files | grep -E "(^|/)\.env$"` returns nothing and `git check-ignore -v backend/.env frontend/.env` shows both ignored.
4. Confirm `frontend/.env` contains **only** `VITE_*` keys and no secret.
5. Confirm the app starts with **optional keys empty** (LLM, embeddings, GitHub token): no crash, AI endpoints return `LLM_UNAVAILABLE`, deterministic features work.
6. Confirm `EMBEDDING_DIM` matches the migrated vector column if pgvector exists.

---

## 6. Website Test Plan (Run After All Fixes)

Use real HTTP calls (`httpx`/`curl`) for the API. If a headless browser is available (Playwright), also drive the UI; if not, say so in the report and rely on API + build + dev-server checks. **Use only small public repositories** for tests (around 20–150 files), and a throwaway test session — do not reuse the owner's data.

**Group 1 — Loading**
1. Backend starts with no traceback; `GET /api/v1/health` → `status:"ok"`, `db:true`, `migrated:true`.
2. `GET /api/v1/meta/capabilities` returns limits and flags.
3. `npm run build` passes; `npm run dev` serves on `:5173`; the landing page returns 200 and renders without console errors; fonts and styles from `design.md` load; theme toggle works (light/dark).
4. Frontend → backend: a request from `http://localhost:5173` succeeds with no CORS error and the `X-Session-Id` header is readable.

**Group 2 — Failure states (must be graceful)**
5. Invalid URL (`http://localhost`, `https://github.com.evil.com/x/y`, empty) → `INVALID_URL`/validation envelope.
6. Non-existent repo → `REPO_NOT_FOUND`. Private repo → `REPO_PRIVATE`.
7. Stop Postgres (or use a wrong URL) → UI shows the database banner; API returns `DATABASE_UNAVAILABLE`, not a 500 traceback.

**Group 3 — Sessions / accounts**
8. First request without `X-Session-Id` creates a session and returns the header; the frontend stores it.
9. Session isolation: repository created in session A returns 404 in session B.
10. If real register/login exists, test it per Section 3; otherwise record “no auth implemented (as specified)”.

**Group 4 — Core flow (happy path)**
11. Analyse a small public repo from the UI/API: job progresses `fetching → parsing → indexing → (embedding) → ready`; the cockpit UI reflects it; Overview shows languages, frameworks, entry points, tree.
12. Explorer: open a file, see highlighting, outline, deep-link `?line=a-b`.
13. Search: keyword and symbol results with line references; semantic/hybrid works or reports `semantic_available:false` cleanly.
14. Dependencies: graph renders; folder collapse; node click opens the file; static-analysis caption visible.
15. Tests page: detected tests and mappings; the “does not run tests” notice is visible.
16. Investigation: paste an issue text (and, if a GitHub token is configured, an issue URL) → ranked evidence with line numbers and `evidence_strength`; with no LLM key, evidence-only results are returned and the UI says AI is unavailable; with a key, hypotheses carry amber **Hypothesis** badges.
17. Plan: generate; steps/risks/impacted files/tests present; export Markdown works; the file contains the disclaimer and no sentence claiming tests ran.

**Group 5 — Trust and security spot-checks**
18. Plant a `.env`-like file with a fake key in a **test fixture repo** → it is absent from file content, search results and API responses.
19. Tar extraction rejects `..` paths and symlinks (unit test).
20. No stack traces or secrets in any API error body or in logs.
21. Rate limit returns `RATE_LIMITED` envelope when exceeded.

**Group 6 — Regression**
22. `pytest backend/tests -q` all green; `npm run build` and `npm run test` green.

---

## 7. Troubleshooting Reference (for the owner’s machine)

| Symptom | Likely cause | Fix |
|---|---|---|
| `asyncio extension requires an async driver … psycopg2` | URL lacks `+asyncpg`, or OS env var overrides `.env` | Fix 2.1; run `echo $env:DATABASE_URL` in PowerShell and `Remove-Item Env:DATABASE_URL` if it prints anything |
| `password authentication failed for user …` | Wrong user/password in `DATABASE_URL` | Match the real Postgres credentials; URL-encode special characters (`@` → `%40`) |
| `database "repopilot" does not exist` | Database not created | `CREATE DATABASE repopilot;` as the `postgres` user |
| `relation "repositories" does not exist` | Migrations not run | `alembic upgrade head` from `backend/` |
| `permission denied to create extension` | User cannot create extensions | As `postgres`, in the `repopilot` DB: `CREATE EXTENSION IF NOT EXISTS pgcrypto; CREATE EXTENSION IF NOT EXISTS pg_trgm;` |
| pgvector not found | Not installed locally | Fine — semantic search is optional; the fallback is FTS/trigram |
| CORS error in the browser console | `FRONTEND_ORIGIN` does not match the dev URL | Use `http://localhost:5173` exactly (no trailing slash) |
| GitHub 403 / rate limit | No `GITHUB_TOKEN` | Add a fine-grained, read-only public-repo token to `backend/.env` |

---

## 8. Deliverable: Diagnostic Report (Required)

When finished, create **`docs/diagnostic_report.md`** (do not commit secrets; masked values only) **and** paste the same content in your final reply. Use this exact structure:

```markdown
# RepoPilot Diagnostic Report
Date/time: <…>   Agent environment: <OS, Python version(s) tested, Node version, Postgres version, Docker yes/no>

## 1. Summary
Overall status: READY / READY WITH LIMITATIONS / NOT READY
One paragraph: what works, what does not.

## 2. Root cause of Error A (psycopg2 / async driver)
Exact cause found (which source supplied the wrong DATABASE_URL, or what code path) and the fix applied. Files changed.

## 3. Fixes applied
| Fix | Files changed | Verified how | Result |
(one row per fix 2.1–2.7)

## 4. Environment check (masked)
- check_env.py output
- backend/.env: missing / empty / unknown / duplicate keys; BOM/CRLF/quote issues; git-ignored? yes/no
- frontend/.env: same
- Effective DATABASE_URL shape: driver/host/port/db (no password); OS override present? yes/no
- Optional keys status: GITHUB_TOKEN, LLM_API_KEY, EMBEDDING_API_KEY (set/empty only)

## 5. Test results (Section 6 of fixed_update.md)
| # | Test | Pass / Fail / Skipped | Evidence (status code, short log line, response shape) | Notes |
Include all 22 tests. For every Skipped, say why (e.g., no browser available, no LLM key).

## 6. Auth finding
Does register/login exist? What was tested? (Anonymous sessions verified: yes/no)

## 7. Python 3.13 compatibility
Packages that failed or were replaced; parser languages that load; ripgrep present? 

## 8. Remaining issues / risks
Ranked list: severity (blocker / major / minor), description, suggested fix, who must act (agent / owner).

## 9. Owner actions needed
Exact, minimal steps for the owner on Windows (commands to run, values to put in .env — without secrets).

## 10. Commands to run the app
Backend, frontend, migrations, tests — exact PowerShell commands from the repo root.
```

**Reporting rules:** be honest — mark anything you did not actually run as *Skipped* or *Not verified*; never write “should work” as a pass. Quote real status codes and log lines (masked). If a gate fails, stop, diagnose, fix, and re-run before continuing.
