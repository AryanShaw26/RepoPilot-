# RepoPilot Diagnostic Report
Date: 2026-11-15   Agent environment: Windows, Python 3.13.9, Node 24.14.0, PostgreSQL 18.4, Docker no

## 1. Summary
Overall status: READY WITH LIMITATIONS

The backend and full frontend are runnable locally. Gemini is now supported for LLM and embedding requests; Anthropic and OpenAI remain supported. Backend tests pass in a fresh Python 3.13.9 venv (54 tests), frontend tests pass (4 tests), and the frontend production build passes. Semantic search remains disabled because pgvector is not installed. Provider retries now apply only to 429/5xx, and investigation retrieval makes no embedding request when semantic storage is unavailable. The authorized live smoke test fetched `pallets/click` once, then encountered Gemini 503 responses. It made exactly five outbound Gemini HTTP requests across the investigation attempt and single plan attempt; neither returned generated content. No `.env` file was edited.

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
- Configured providers are `gemini`, now implemented for both LLM and embeddings. Runtime capabilities report `llm_available=true`, `semantic_search=false` because pgvector is absent. No actual `.env` files were edited.

## 5. Test results (Section 6 of fixed_update.md)
| # | Test | Pass / Fail / Skipped | Evidence (status code, short log line, response shape) | Notes |
|---:|---|---|---|---|
| 1 | Backend startup and health | Pass | `GET /api/v1/health` 200: `status=ok`, `db=true`, `migrated=true` | Python 3.13.9 |
| 2 | Capabilities | Pass | Gemini configured and reported `llm_available=true`; unsupported-provider test confirms `llm_available=false` plus a reason; semantic search false | pgvector absent |
| 3 | Landing page, styles, theme | Pass | Vite page 200; browser rendered landing page, fonts/styles, theme toggle, and `/styleguide` | Theme persistence verified; no browser console errors in final checks |
| 4 | Frontend/backend CORS and session header | Pass | OPTIONS 200; allowed `Content-Type`/`X-Session-Id`; response exposed `X-Session-Id` | Origin-bearing request verified |
| 5 | Invalid repository URLs | Pass | Invalid/empty URL requests returned 400 `INVALID_ARGUMENT` | API client handles `INVALID_URL` and `INVALID_ARGUMENT` |
| 6 | Missing and private repositories | Skipped | Missing repository returned 404 `REPO_NOT_FOUND` | Private-repository case not tested; public-only authorization |
| 7 | Database failure and UI banner | Pass | Degraded health; DB-dependent request 503 `DATABASE_UNAVAILABLE`; UI displayed database-not-ready banner | Isolated wrong-password run; no traceback/credential in response |
| 8 | First anonymous session | Pass | Request without `X-Session-Id` created session; frontend stored returned UUID | Test state later restored/cleaned |
| 9 | Session isolation | Pass | Repository request from a separate session returned 404 `REPO_NOT_FOUND` | Throwaway test data removed |
| 10 | Register/login | Pass | No register/login endpoints; anonymous session flow is implemented as specified | No account system added |
| 11 | Repository analysis happy path | Pass | Small public repo reached `ready`; job polling and overview/tree endpoints returned results | `fetching` â†’ `parsing` â†’ `indexing` â†’ `ready`; embedding skipped because unavailable |
| 12 | Explorer and file deep-link | Pass | File deep link highlighted five requested lines; syntax highlighting and symbol outline links rendered | Browser verified |
| 13 | Keyword/symbol/semantic search | Pass | Keyword and symbol searches each returned 20 results | Semantic unavailable; explicit fallback displayed |
| 14 | Dependency graph | Pass | Graph rendered 47 file nodes and 8 folder nodes; folder collapse and node navigation worked | Duplicate edge IDs fixed; final graph had no console errors |
| 15 | Test detection and mappings | Pass | Tests page showed six test files and the â€œdoes not run testsâ€ notice | No repository tests were executed |
| 16 | Investigation | Skipped (live Gemini) | Mocked Gemini JSON and one-repair tests pass; live `pallets/click` request attempts returned 503 | Five-call total cap respected; no live hypotheses were returned |
| 17 | Plan generation/export | Skipped (live Gemini) | Plan schema, path validator, export rendering, and frontend tests pass; final live Gemini plan request returned 503 | No live plan was returned |
| 18 | Secret-like file filtering | Pass (mocked tarball flow) | `respx` served a GitHub tarball with `.env`, `.pem`, and a fake token; extraction/scanning excluded or redacted all three, and secret strings were absent from indexed content, `search_ripgrep` results, evidence/prompt, plan export, and captured logs | No external GitHub request in this test |
| 19 | Archive traversal and symlink rejection | Pass | Backend unit tests reject `..` paths and symlinks | Included in 53 passing backend tests |
| 20 | No secrets/tracebacks in errors and logs | Pass | Tested provider/API error paths returned sanitized envelopes; no secret values printed | Limited to exercised paths |
| 21 | Rate limiting | Pass | Analysis endpoint: first five invalid requests returned 400; sixth returned 429 `RATE_LIMITED` | No GitHub call required |
| 22 | Regression gates | Pass | Fresh Python 3.13.9 venv install; backend: 54 passed; frontend: 4 passed; `npm run build` passed | `check_env.py`: Skipped this turn |

Live Gemini request accounting: 5 Gemini HTTP requests total (1 initial investigation request interrupted while waiting, 3 transient retry requests returning 503, and 1 single plan request returning 503). One additional public `pallets/click` codeload tarball GET was made. No other live Gemini calls were made. The code path renders every hypothesis through `Statement(kind="hypothesis")`, which maps to the amber `Hypothesis` badge; live badge rendering with generated data was skipped because Gemini returned no content. The validator's valid/invalid evidence reference behavior is covered by automated tests.

## 6. Auth finding
Register/login does not exist. Anonymous sessions are the implemented model. First-session creation/storage and isolation between two sessions were verified: yes.

## 7. Python 3.13 compatibility
Python 3.13.9 fresh venv install and all 54 backend tests passed. Per-language Tree-sitter packages are used; Python, JavaScript, and TypeScript parsing are covered. `rg` is available.

## 8. Remaining issues / risks
1. **Major - provider availability:** Gemini LLM requests returned HTTP 503 during the live smoke run. Mocked provider tests pass; retry after Gemini is available to validate generated investigation and plan content end to end.
2. **Minor â€” owner:** Semantic search is disabled because pgvector is absent. Install/enable pgvector and run migrations if semantic search is required; keyword/symbol fallback works.
3. **Minor - agent/owner:** The secret-filter tarball-to-scan flow passed with downstream content assertions. Search/evidence/prompt/export portions used in-test sanitized data rather than database-backed API ingestion.
4. **Minor â€” owner:** Private GitHub repository handling was not tested; only public repositories were authorized.
5. **Live verification limitation:** Generated hypotheses, plan contents, valid live evidence references, and live badge rendering were skipped because Gemini returned 503. The UI source uses the amber `Hypothesis` badge for hypothesis-authored text.

## 9. Owner actions needed
1. No action is needed to run deterministic/local features.
2. Retry the live Gemini investigation and plan smoke test once the Gemini endpoint is available; configured credentials were not displayed or changed.
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
