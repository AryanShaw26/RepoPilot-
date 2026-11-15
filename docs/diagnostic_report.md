# RepoPilot Diagnostic Report
Date/time: 2026-11-15 13:36 +05:30   Agent environment: Windows, Python 3.13.9, Node 24.14.0, PostgreSQL 18.4, Docker no

## 1. Summary
Overall status: READY WITH LIMITATIONS

The backend and full frontend are runnable locally: the API, analysis workflow, explorer, search, dependency graph, tests, investigation, plans/export, styleguide, and theme controls were exercised; the backend suite (42 tests), frontend suite (4 tests), production build, migrations, and masked environment check passed. AI-backed features are unavailable because `LLM_PROVIDER` and `EMBEDDING_PROVIDER` are set to unsupported `gemini`; semantic search is also unavailable because pgvector is not installed. The first investigation smoke test inadvertently triggered about 18 embedding retries, exceeding the requested five-call limit; this was stopped/fixed, and no further external LLM/embedding calls were made.

## 2. Root cause of Error A (psycopg2 / async driver)
The current owner `.env` resolves to `postgresql+asyncpg` and no OS `DATABASE_URL` override was found. The failure was in the settings/database URL code path: environment loading and PostgreSQL scheme normalization were not reliably centralized, allowing a URL without an explicit async driver to reach SQLAlchemy. A canonical, absolute-path, BOM-safe settings loader and URL validator now normalize supported PostgreSQL schemes to `postgresql+asyncpg` before the lazy engine is created. The configured database connection and migration state were verified; no `.env` file was edited.

## 3. Fixes applied
| Fix | Files changed | Verified how | Result |
|---|---|---|---|
| 2.1 Canonical settings and URL normalization | `backend/app/core/config.py`, backend settings imports, `backend/tests/test_config.py` | URL/scheme, quoting, SSL parameter, BOM/CRLF tests; masked diagnostics | Pass; asyncpg effective, no OS override |
| 2.2 Lazy database layer | `backend/app/db/session.py` | Python 3.13 import smoke and full backend suite | Pass; imports without eager DB connection |
| 2.3 Alembic URL consistency | `backend/alembic/env.py`, migrations, `backend/alembic.ini` | `alembic upgrade head` twice | Pass; second run no-op |
| 2.4 Graceful degradation and health | `backend/app/main.py`, API health/error handling, cleanup service and tests | Healthy and wrong-password runs; health degraded and DB request returned 503 `DATABASE_UNAVAILABLE` | Pass; no traceback in tested error response |
| 2.5 Python 3.13 compatibility | `backend/app/services/parser.py`, `backend/requirements.txt`, `README.md`, tests | Python 3.13.9 import; Python/JavaScript/TypeScript parser tests; 42 backend tests | Pass in the current Python 3.13 environment |
| 2.6 Environment diagnostics | `backend/scripts/check_env.py` | Ran from `backend/`; masked report and DB/extension checks | Pass; exit 0 |
| 2.7 Frontend connectivity and CORS | `frontend/src/App.tsx`, `frontend/src/api/client.ts`, `frontend/.env.example`, `backend/app/main.py`, tests | Browser health banner, live CORS preflight/header checks, frontend tests/build | Pass |

**Route audit (PRD section 8 vs implemented `/api/v1` routes):** no gaps found. Health/meta: `GET /health`, `GET /meta/capabilities`. Repositories: `POST /repositories`, `GET /repositories`, `GET /repositories/{repo_id}`, `DELETE /repositories/{repo_id}`, `GET /repositories/{repo_id}/job`, `POST /repositories/{repo_id}/reanalyse`. Explorer: `GET /repositories/{repo_id}/tree`, `GET /repositories/{repo_id}/files`, `GET /repositories/{repo_id}/files/symbols`, `POST /repositories/{repo_id}/symbols/{symbol_id}/explain`, `GET /repositories/{repo_id}/symbols`. Search: `POST /repositories/{repo_id}/search`. Dependencies: `GET /repositories/{repo_id}/graph`, `GET /repositories/{repo_id}/files/dependencies`. Investigations: `POST /repositories/{repo_id}/investigations`, `GET /investigations/{inv_id}`, `GET /repositories/{repo_id}/investigations`. Plans: `POST /investigations/{inv_id}/plan`, `GET /plans/{plan_id}`, `GET /plans/{plan_id}/export`. Test intelligence: `GET /repositories/{repo_id}/tests`, `GET /repositories/{repo_id}/tests/for`, `POST /investigations/{inv_id}/test-recommendations`. `DATABASE_UNAVAILABLE` and `INVALID_ARGUMENT` were added to PRD section 8. `backend/pytest.ini` sets `asyncio_default_fixture_loop_scope`; `frontend/.env.example` contains `VITE_API_BASE_URL`.

## 4. Environment check (masked)
- `check_env.py`: **PASS**. PostgreSQL connection/schema checks pass; `pgcrypto` and `pg_trgm` installed; `vector` not installed; ripgrep available; snapshot directory writable.
- `backend/.env`: missing/empty/unknown/duplicate keys none; BOM no; surrounding quotes none; CRLF differs from LF example; git-ignored yes.
- `frontend/.env`: missing/empty/unknown/duplicate keys none; BOM no; surrounding quotes none; CRLF differs from LF example; only VITE keys and no secret-key names; git-ignored yes.
- Both `.env.example` key sets match PRD section 11; `frontend/.env.example` contains only the expected `VITE_*` keys.
- Effective `DATABASE_URL` shape: driver `postgresql+asyncpg`, host `localhost`, port `5432`, database `repopilot`; OS override present: no.
- Optional keys: `GITHUB_TOKEN` set; `LLM_API_KEY` set; `EMBEDDING_API_KEY` set. Values not displayed.
- Configured providers are `gemini`, which this codebase does not implement. Runtime capabilities: `llm_available=false`, `semantic_search=false`. No actual `.env` files were edited.

## 5. Test results (Section 6 of fixed_update.md)
| # | Test | Pass / Fail / Skipped | Evidence (status code, short log line, response shape) | Notes |
|---:|---|---|---|---|
| 1 | Backend startup and health | Pass | `GET /api/v1/health` 200: `status=ok`, `db=true`, `migrated=true` | Python 3.13.9 |
| 2 | Capabilities | Pass | `GET /api/v1/meta/capabilities` 200; limits returned; `llm_available=false`, `semantic_search=false` | Providers/pgvector unavailable |
| 3 | Landing page, styles, theme | Pass | Vite page 200; browser rendered landing page, fonts/styles, theme toggle, and `/styleguide` | Theme persistence verified; no browser console errors in final checks |
| 4 | Frontend/backend CORS and session header | Pass | OPTIONS 200; allowed `Content-Type`/`X-Session-Id`; response exposed `X-Session-Id` | Origin-bearing request verified |
| 5 | Invalid repository URLs | Pass | Invalid/empty URL requests returned 400 `INVALID_ARGUMENT` | API client handles `INVALID_URL` and `INVALID_ARGUMENT` |
| 6 | Missing and private repositories | Skipped | Missing repository returned 404 `REPO_NOT_FOUND` | Private-repository case not tested; public-only authorization |
| 7 | Database failure and UI banner | Pass | Degraded health; DB-dependent request 503 `DATABASE_UNAVAILABLE`; UI displayed database-not-ready banner | Isolated wrong-password run; no traceback/credential in response |
| 8 | First anonymous session | Pass | Request without `X-Session-Id` created session; frontend stored returned UUID | Test state later restored/cleaned |
| 9 | Session isolation | Pass | Repository request from a separate session returned 404 `REPO_NOT_FOUND` | Throwaway test data removed |
| 10 | Register/login | Pass | No register/login endpoints; anonymous session flow is implemented as specified | No account system added |
| 11 | Repository analysis happy path | Pass | Small public repo reached `ready`; job polling and overview/tree endpoints returned results | `fetching` → `parsing` → `indexing` → `ready`; embedding skipped because unavailable |
| 12 | Explorer and file deep-link | Pass | File deep link highlighted five requested lines; syntax highlighting and symbol outline links rendered | Browser verified |
| 13 | Keyword/symbol/semantic search | Pass | Keyword and symbol searches each returned 20 results | Semantic unavailable; explicit fallback displayed |
| 14 | Dependency graph | Pass | Graph rendered 47 file nodes and 8 folder nodes; folder collapse and node navigation worked | Duplicate edge IDs fixed; final graph had no console errors |
| 15 | Test detection and mappings | Pass | Tests page showed six test files and the “does not run tests” notice | No repository tests were executed |
| 16 | Investigation | Pass | UI returned 202; completed investigation showed 10 ranked evidence results, line references, moderate evidence strength, and AI-unavailable status | No generated hypotheses. Initial smoke caused about 18 embedding retries, exceeding the requested cap; retries were fixed and no further external AI calls were made. |
| 17 | Plan generation/export | Pass | UI plan returned 201 with four steps; export returned 200 Markdown containing disclaimer and no claim that tests ran | Evidence-rich plan rendering verified |
| 18 | Secret-like file filtering | Skipped | Full fixture-repository ingestion-to-search/API end-to-end check was not run | Backend unit test passed for `.env.production` exclusion and token-bearing content redaction |
| 19 | Archive traversal and symlink rejection | Pass | Backend unit tests reject `..` paths and symlinks | Included in 42 passing backend tests |
| 20 | No secrets/tracebacks in errors and logs | Pass | Tested provider/API error paths returned sanitized envelopes; no secret values printed | Limited to exercised paths |
| 21 | Rate limiting | Pass | Analysis endpoint: first five invalid requests returned 400; sixth returned 429 `RATE_LIMITED` | No GitHub call required |
| 22 | Regression gates | Pass | Backend: 42 passed; frontend: 4 passed; `npm run build` passed; `check_env.py` passed | Python 3.13.9 |

## 6. Auth finding
Register/login does not exist. Anonymous sessions are the implemented model. First-session creation/storage and isolation between two sessions were verified: yes.

## 7. Python 3.13 compatibility
Python 3.13.9 import smoke and all 42 backend tests passed. Per-language Tree-sitter packages are used; Python, JavaScript, and TypeScript parsing were tested. A fresh isolated venv install was not separately performed. `rg` is available.

## 8. Remaining issues / risks
1. **Major — owner:** AI-backed explanations, investigation hypotheses, plans, and embeddings are unavailable because configured provider `gemini` is unsupported. Change to a provider implemented by the app (`openai` or `anthropic`) with its corresponding key if AI features are needed.
2. **Minor — owner:** Semantic search is disabled because pgvector is absent. Install/enable pgvector and run migrations if semantic search is required; keyword/symbol fallback works.
3. **Minor — agent/owner:** Full secret-filter end-to-end fixture check was skipped; unit-level exclusion/redaction coverage passed. Run the full fixture flow before relying on that end-to-end guarantee.
4. **Minor — owner:** Private GitHub repository handling was not tested; only public repositories were authorized.
5. **Process incident — agent:** Initial smoke testing triggered about 18 embedding retries, above the requested maximum of five calls. Retry behavior was fixed; no additional external AI calls were made.

## 9. Owner actions needed
1. No action is needed to run deterministic/local features.
2. For AI features, set `LLM_PROVIDER` to `openai` or `anthropic` and use the matching configured API key; for embeddings, use a supported embedding provider.
3. For semantic search, install PostgreSQL pgvector and run the migration. It is optional for current keyword/symbol search.
4. No `.env` file needs to be edited for the verified local startup; do not share or commit secrets.

## 10. Commands to run the app
From the repository root in PowerShell, start the backend:

```powershell
Set-Location .\backend
.\.venv\Scripts\Activate.ps1
alembic upgrade head
uvicorn app.main:app --reload
```

In another PowerShell window, start the frontend:

```powershell
Set-Location .\frontend
npm run dev
```

Validation commands:

```powershell
Set-Location .\backend
python -c "import app.main"
python -m pytest tests -q
python scripts/check_env.py
Set-Location ..\frontend
npm run test
npm run build
```
