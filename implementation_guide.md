# RepoPilot — Implementation Guide (Build Order for the AI Agent)

> **Goal:** Build the complete, working RepoPilot application in one run, in the correct dependency order.
> **Read first:** `prd.md` (what to build: architecture, schema, endpoints, env, `.gitignore`) and `design.md` (how it looks).
> **This file:** *what to build first, what next, and how to verify each step before moving on.*

---

## 0. Operating Rules for the Agent

1. **Follow the phase order.** Each phase ends with a **Gate** (a command or check). Do not start the next phase until the gate passes. If a gate fails, fix it before continuing.
2. **Backend before frontend.** The frontend is built against a working API.
3. **Deterministic before AI.** Every feature must work without an LLM key first; AI layers on top and degrades gracefully (`LLM_UNAVAILABLE`).
4. **Never execute code from analysed repositories.** No `exec`, no `eval`, no install scripts, no `git clone` hooks.
5. **Never commit secrets.** Create `.gitignore` in Phase 0, *before* any `.env` exists. Only `.env.example` files are committed.
6. **Use tokens, not hard-coded colours**, in the frontend (see `design.md` §2).
7. **Commit after each phase** with message `phase N: <name>`.
8. **If time is short**, follow the cut-line in §14 — never skip the trust features (facts vs hypotheses, validator, secret exclusion).
9. When a detail is unspecified, pick the simplest option consistent with `prd.md` §2 (Guiding Principles) and note the assumption in `README.md`.

---

## 1. Build Order Overview

```
Phase 0  Repo scaffolding, .gitignore, env templates, docker-compose
Phase 1  Backend foundation (config, DB, models, migrations, errors, health)
Phase 2  GitHub service + URL validation + repository/job endpoints
Phase 3  Ingest pipeline (download → safe extract → filter → secrets scan → persist files)
Phase 4  Parser (Tree-sitter): symbols + imports + import resolution
Phase 5  Search (FTS, ripgrep, symbol, trigram) + explorer endpoints
Phase 6  Dependency graph service + endpoints
Phase 7  Test intelligence (detection + mapping)
Phase 8  Embeddings + semantic search + hybrid fusion (pgvector, with fallback)
Phase 9  LLM service + validator + Investigations
Phase 10 Contribution planner + test recommendations + Markdown export
Phase 11 Frontend foundation (Vite, Tailwind tokens, UI kit, API client, routing)
Phase 12 Frontend pages: Landing → Analysing → Overview
Phase 13 Frontend: Explorer + Search
Phase 14 Frontend: Dependencies graph
Phase 15 Frontend: Issues → Investigation → Plan → Tests
Phase 16 Hardening: rate limits, cleanup, error states, accessibility, tests
Phase 17 Deployment (Render + Vercel) + README + demo seed
```

Dependency logic: 1→2→3→4 are strictly sequential (each feeds the next). 5, 6, 7 depend on 4. 8 depends on 3–4. 9 depends on 5 + 8 (but works with 5 alone if semantic is off). 10 depends on 6, 7, 9. Frontend 11 can start once Phase 2 endpoints exist, but pages are built after their backend phase is complete.

---

## 2. Phase 0 — Scaffolding

**Tasks**
1. Create the monorepo structure from `prd.md` §13 (empty `__init__.py` files where needed).
2. Write the root `.gitignore` exactly as in `prd.md` §12 **first**.
3. Create `backend/.env.example` and `frontend/.env.example` exactly as in `prd.md` §11. Copy to `backend/.env` and `frontend/.env` for local use (git-ignored).
4. `docker-compose.yml`:
   - `db`: image `pgvector/pgvector:pg16`, env `POSTGRES_USER=repopilot`, `POSTGRES_PASSWORD=change_me`, `POSTGRES_DB=repopilot`, port `5432`, named volume.
   - (Optional) `backend` and `frontend` services for full-stack compose.
5. `backend/requirements.txt` (pin versions):
   `fastapi, uvicorn[standard], pydantic>=2, pydantic-settings, sqlalchemy[asyncio]>=2, asyncpg, alembic, httpx, tree-sitter, tree-sitter-languages (or per-language wheels), slowapi, structlog, python-multipart, pytest, pytest-asyncio, anyio, respx, openai, anthropic, numpy`
6. `backend/Dockerfile`: python:3.11-slim; `apt-get install -y ripgrep`; install requirements; `CMD` runs `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}`.

**Gate:** `docker compose up -d db` → `psql` connects; `git status` shows `.env` files are **not** tracked.

---

## 3. Phase 1 — Backend Foundation

**Files:** `core/config.py`, `core/logging.py`, `core/errors.py`, `db/base.py`, `db/session.py`, `db/models.py`, `main.py`, `api/v1/health.py`, `alembic/`.

**Tasks**
1. `config.py`: `Settings(BaseSettings)` with every variable in `prd.md` §11.1, typed, with defaults; `@lru_cache get_settings()`.
2. `errors.py`: `class AppError(Exception)` with `code`, `message`, `status_code`, `details`; exception handlers returning the standard envelope (`prd.md` §8). Map validation errors → `VALIDATION_ERROR`.
3. `db/session.py`: async engine + `async_sessionmaker`; FastAPI dependency `get_db`.
4. `models.py`: SQLAlchemy 2.0 models for **every table** in `prd.md` §7.3 (use `Mapped[...]`, `JSONB`, `ARRAY(Text)`, `TSVECTOR`). The `embedding` column is **not** declared in the ORM; it is added by migration 0002 and accessed via raw SQL.
5. Alembic: async env.py; migration `0001_init` (extensions `pgcrypto`, `pg_trgm` + all tables/indexes). Migration `0002_pgvector`: wrap in try/except; if `CREATE EXTENSION vector` works, `ALTER TABLE code_chunks ADD COLUMN embedding vector(:EMBEDDING_DIM)` and create the HNSW index.
6. `main.py`: app factory; CORS (`FRONTEND_ORIGIN` only); register routers under `API_V1_PREFIX`; lifespan: check DB, detect pgvector (`semantic_enabled` stored in `app.state`), start the cleanup scheduler stub.
7. Session middleware/dependency `get_session_id`: read `X-Session-Id`; if missing/invalid, create a `sessions` row and set the response header; expose header via CORS `expose_headers=["X-Session-Id"]`.
8. `health.py`: `GET /health`, `GET /meta/capabilities`.

**Gate:** `alembic upgrade head` succeeds; `uvicorn` starts; `GET /api/v1/health` returns `{status:"ok", db:true, semantic_enabled:true|false}`.

---

## 4. Phase 2 — GitHub Service, Repositories & Jobs

**Files:** `services/github.py`, `schemas/repository.py`, `api/v1/repositories.py`, `workers/jobs.py`.

**Tasks**
1. `parse_github_url(url) -> (owner, repo, branch|None)`: strict regex; host must equal `github.com`; reject anything else with `INVALID_URL`. Strip `.git` suffix and trailing slashes. Unit-test with good/bad/SSRF-style inputs (`http://localhost`, `github.com.evil.com`, `@` tricks).
2. `GitHubService` (httpx.AsyncClient, base `GITHUB_API_BASE`, optional bearer token, timeouts):
   - `get_repo(owner, repo)` → metadata (404 → `REPO_NOT_FOUND`; 403 + `x-ratelimit-remaining: 0` → `GITHUB_RATE_LIMIT`; private → `REPO_PRIVATE`).
   - `get_languages`, `get_branch_sha`, `get_issue(owner, repo, number)` (with first ~10 comments).
   - `download_tarball(owner, repo, ref, dest_path)` streams to disk, aborts when bytes > `MAX_REPO_SIZE_MB` (`REPO_TOO_LARGE`).
3. Job runner (`workers/jobs.py`): `async def run_analysis(repository_id)` launched with `asyncio.create_task` (keep a module-level set of tasks to avoid GC). It updates `analysis_jobs.stage/progress/message` in its **own DB session**, wraps everything in `asyncio.wait_for(..., ANALYSIS_TIMEOUT_S)`, and on any exception sets `stage='failed'`, stores a *safe* error message, and sets `repositories.status='failed'`.
4. Endpoints in `repositories.py`: `POST /repositories`, `GET /repositories`, `GET /repositories/{id}`, `DELETE`, `GET /{id}/job`, `POST /{id}/reanalyse`. Enforce session ownership (404 otherwise). `POST` creates the repository + job rows, fetches metadata synchronously (fast fail), then schedules the background task and returns `202`.
5. For now the background task only runs the `fetching` stage (metadata + tarball download to `SNAPSHOT_DIR`), sets progress to 20.

**Gate:** POST a real small public repo URL → `202`; polling `/job` shows `queued → fetching`; invalid URL returns `INVALID_URL`; non-existent repo returns `REPO_NOT_FOUND`.

---

## 5. Phase 3 — Ingest Pipeline (Extract, Filter, Persist)

**Files:** `services/ingest.py`, `services/languages.py`, `services/secrets.py`.

**Tasks**
1. **Safe extraction** (critical):
   ```python
   def safe_extract(tar_path, dest):
       with tarfile.open(tar_path, "r:gz") as tar:
           for m in tar:
               target = os.path.realpath(os.path.join(dest, m.name))
               if not target.startswith(os.path.realpath(dest) + os.sep): continue   # zip-slip
               if m.issym() or m.islnk() or m.isdev(): continue                        # no links/devices
               if m.isfile() and m.size > MAX_FILE_BYTES * 20: continue
               tar.extract(m, dest, set_attrs=False)
   ```
   GitHub tarballs contain a single top-level folder (`owner-repo-sha/`); strip it so paths are repo-relative.
2. **File walk & filter:** apply exclusion rules from `prd.md` §9.2 (directories, extensions, size, binary detection by NUL byte in first 8 KB). Stop at `MAX_FILES`.
3. **Language detection:** extension map in `languages.py` (py, js, jsx, ts, tsx, java, go, rs, rb, php, c, cpp, h, cs, kt, swift, md, json, yml, toml, sh, sql, html, css…). Mark Tree-sitter-supported languages (Python, JS/JSX, TS/TSX, Java, Go minimum).
4. **Secrets scan** (`secrets.py`): regex set (AWS `AKIA[0-9A-Z]{16}`, GitHub `gh[pousr]_[A-Za-z0-9]{36,}`, `sk-[A-Za-z0-9]{20,}`, `-----BEGIN (RSA|EC|OPENSSH|PRIVATE) KEY-----`, generic `(?i)(api[_-]?key|secret|token|passwd|password)\s*[:=]\s*['"][^'"]{12,}['"]`). On hit: `content=NULL`, flag via `sha1` + a logged warning (no secret in log). These files are excluded from chunking, search, and LLM input.
5. **Persist:** bulk insert `repo_files` (`content`, `line_count`, `directory`, `is_test` by convention, `content_tsv = to_tsvector('simple', content)` using `unaccent`-free simple config for code). Use `executemany`/`insert().values([...])` in batches of 200.
6. **Repository facts:** compute language byte totals, detect frameworks from manifests (parse `package.json` dependencies, `requirements.txt`, `pyproject.toml`, `pom.xml`, `go.mod`, `Cargo.toml`) and map known package names → framework names (React, Next.js, Vue, Express, FastAPI, Django, Flask, Spring, Gin, etc.); detect entry points via heuristics in `prd.md` §3.1; capture a README excerpt (first ~1,500 chars).
7. Update job: `parsing` 20→50 (file walk), then proceed to Phase 4's hooks. Set `snapshot_expires_at`.

**Gate:** analyse a small repo → `repo_files` populated, `repositories.frameworks/entry_points/languages` filled; a planted `.env` file in a test fixture is **absent** from `repo_files.content`.

---

## 6. Phase 4 — Parser: Symbols, Imports, Resolution

**Files:** `services/parser.py`, `services/imports.py`.

**Tasks**
1. `parser.py`: load Tree-sitter parsers per language; function `extract_symbols(language, source_bytes) -> list[Symbol]` using node-type walks:
   - **Python:** `function_definition`, `class_definition` (methods = functions inside classes → `kind='method'`, set `parent`); docstring = first string expression statement.
   - **JS/TS:** `function_declaration`, `class_declaration`, `method_definition`, `lexical_declaration` with arrow/function expressions, `interface_declaration`, `type_alias_declaration`, `enum_declaration`; handle `export` wrappers.
   - **Java:** `class_declaration`, `interface_declaration`, `method_declaration`, `enum_declaration`.
   - **Go:** `function_declaration`, `method_declaration`, `type_declaration`.
   Capture `name`, `kind`, `start_line`/`end_line` (1-based), `signature` (first line, truncated to 200 chars). Wrap each file in try/except: a parse failure must never fail the job (log and continue).
2. `extract_imports(language, source_bytes) -> list[RawImport]` (specifier, line):
   - Python: `import_statement`, `import_from_statement` (preserve relative level).
   - JS/TS: `import_statement`, `export ... from`, `call_expression` where callee is `require` with a string literal argument. Dynamic `import()` with a literal string is allowed; non-literal is ignored.
   - Java: `import_declaration`. Go: `import_spec`.
3. `imports.py` — **resolution** to repo files:
   - JS/TS: relative specifiers (`./`, `../`) → try extensions `.ts .tsx .js .jsx .mjs .cjs` and `/index.*`; honour simple `tsconfig.json` `paths`/`baseUrl` if present (best effort); bare specifiers → external (`package_name` = first segment, or `@scope/name`).
   - Python: convert dotted module → path candidates (`a/b/c.py`, `a/b/c/__init__.py`) relative to repo root and to each detected source root (`src/`, top-level package dirs); relative imports resolved from the importing file's package; unresolved → external with top-level package name.
   - Java: map fully-qualified class → `src/main/java/.../Class.java` by suffix match. Go: module path prefix from `go.mod` → directory.
   - Unresolved internal-looking specifiers keep `target_file_id = NULL`, `is_external=false`, and are counted in graph stats as "unresolved".
4. Persist `symbols` and `file_imports` in batches; create `code_chunks` (one chunk per top-level symbol up to 120 lines; remaining text in 60-line windows with 10-line overlap; skip generated/minified; cap `MAX_CHUNKS_PER_REPO`); fill `content_tsv`.
5. Job: `parsing` → `indexing` (50→75).

**Gate:** On a fixture repo (create `backend/tests/fixtures/sample_repo/` with ~10 Python + JS files and known imports), unit tests assert exact symbol names/line numbers and import edges.

---

## 7. Phase 5 — Search & Explorer Endpoints

**Files:** `services/search.py`, `api/v1/explorer.py`, `api/v1/search.py`, `schemas/search.py`.

**Tasks**
1. **Keyword search via ripgrep** (when snapshot exists) — never through a shell:
   ```python
   proc = await asyncio.create_subprocess_exec(
       "rg", "--json", "--max-count", "5", "--max-filesize", "300K",
       "--glob", "!{.git,node_modules,dist,build}", "--ignore-case", "--fixed-strings",
       "--", query, snapshot_dir, stdout=PIPE, stderr=PIPE)
   # wait_for(communicate(), timeout=5); parse JSON lines; cap total results
   ```
   Convert absolute paths back to repo-relative; skip paths of secret-flagged files.
   **Fallback** when no snapshot: Postgres `content_tsv @@ plainto_tsquery` + trigram `ILIKE` on lines of `code_chunks`.
2. **Symbol search:** `symbols.name ILIKE`/`% similarity` with `pg_trgm`, ordered by exact > prefix > trigram similarity.
3. **Result shape:** `{file_path, start_line, end_line, snippet, score, source}` where `snippet` is ≤ 12 lines with 2 lines of context.
4. **Explorer endpoints:** `tree`, `files` (content from DB; 404 if secret-flagged/binary with a clear message), `files/symbols`, `symbols`. Directory listing computed from `repo_files.directory`/`path`.
5. `POST /search` supports `mode` = `keyword|symbol|semantic|hybrid`; `semantic`/`hybrid` return `semantic_available:false` and fall back gracefully until Phase 8.
6. Add a unit test for the query sanitiser: length cap 500, strip NULs, `--` terminator is always present.

**Gate:** search for a known identifier in the fixture repo returns the exact file/line; file endpoint returns content and line count.

---

## 8. Phase 6 — Dependency Graph

**Files:** `services/graph.py`, `api/v1/graph.py`, `schemas/graph.py`.

**Tasks**
1. Build the graph from `file_imports` (internal edges only by default; `include_external=true` adds package nodes).
2. Compute `in_degree`, `out_degree`; detect cycles with an iterative Tarjan SCC (components of size > 1 = cycles) — **no recursion** (stack safety).
3. `level=folder`: aggregate files into folder nodes by `path_prefix` depth and aggregate edge counts (`weight`).
4. Return at most 800 nodes; if exceeded, auto-switch to folder level and say so in `stats.note`.
5. `GET /files/dependencies?path=` returns direct imports / imported-by lists (with line numbers).
6. Export helper `reverse_dependencies(file_ids, depth=2)` for the planner (facts).

**Gate:** On the fixture repo the graph matches the expected edge list; a planted cycle is reported.

---

## 9. Phase 7 — Test Intelligence

**Files:** `services/test_intel.py`, `api/v1/tests.py`.

**Tasks**
1. Test file detection (set `repo_files.is_test`): patterns `test_*.py`, `*_test.py`, `*_test.go`, `*.test.(js|ts|jsx|tsx)`, `*.spec.(js|ts|jsx|tsx)`, `*Test.java`, `*Tests.java`, directories `tests/`, `test/`, `__tests__/`, `spec/`.
2. Framework detection: pytest (`pytest` in deps / `conftest.py`), unittest, jest/vitest (deps + config files), JUnit, Go `testing`.
3. Mapping (`test_mappings`): (a) **name convention** `foo.py ↔ test_foo.py` → `high`; (b) **import analysis**: test file imports source file → `high`/`medium` (based on direct vs transitive); (c) **directory proximity** `src/a/b.ts ↔ tests/a/b.test.ts` → `medium`/`low`.
4. Endpoints: `GET /tests`, `GET /tests/for?path=`. Compute "% of source files with ≥ 1 mapped test" as a *coverage-proxy*, labelled "not code coverage".
5. All outputs here are **facts** (`kind: "fact"`). Never imply execution.

**Gate:** Fixture repo returns correct mappings and framework detection.

---

## 10. Phase 8 — Embeddings & Hybrid Retrieval

**Files:** `services/embeddings.py`, `services/retrieval.py`.

**Tasks**
1. `EmbeddingService.embed(texts) -> list[list[float]]` using `EMBEDDING_PROVIDER`; batches of 64; retry with exponential backoff (3 tries); truncate each text to ~8,000 chars. If no API key → raise `FeatureDisabled`; semantic is then off.
2. Embedding stage in the job (75→98 %): iterate `code_chunks` without embeddings, embed, and `UPDATE code_chunks SET embedding = :vec` (pass vectors as `'[...]'::vector` strings). Skip entirely if `semantic_enabled` is false or the key is missing; log it once.
3. `semantic_search(repo_id, query, limit)`: embed query → `ORDER BY embedding <=> :qvec LIMIT :n` (cosine). Return chunks with file path and line range.
4. `hybrid_search`: gather keyword, symbol, semantic lists → **Reciprocal Rank Fusion** with `k=60`:
   ```python
   def rrf(rank_lists, k=60):
       scores = defaultdict(float); sources = defaultdict(set)
       for name, items in rank_lists.items():
           for rank, key in enumerate(items, 1):
               scores[key] += 1.0 / (k + rank); sources[key].add(name)
       return sorted(scores.items(), key=lambda kv: -kv[1]), sources
   ```
   Group by chunk/file+line range; merge overlapping ranges.
5. Wire into `POST /search` (modes `semantic` and `hybrid`) and set `semantic_available` correctly.

**Gate:** With a key: semantic query returns relevant chunks; without a key or without pgvector: hybrid still works using keyword + symbol and the response says `semantic_available:false`.

---

## 11. Phase 9 — LLM Service, Validator, Investigations

**Files:** `services/llm.py`, `services/validator.py`, `services/investigate.py`, `prompts/*.py`, `api/v1/investigations.py`, `schemas/investigation.py`.

**Tasks**
1. `LLMService.complete_json(system, user, schema_model)`: provider switch (Anthropic/OpenAI) via SDK; temperature `LLM_TEMPERATURE`; max tokens `LLM_MAX_OUTPUT_TOKENS`; request JSON only; parse; validate against a Pydantic model; **one repair retry**; raise `LLM_UNAVAILABLE` if the key is missing or calls fail. Never log prompts containing code beyond DEBUG, and never log keys.
2. **Term extraction** (deterministic, no LLM): from issue text extract identifiers (camelCase/snake_case/dotted names, backticked tokens), error strings (quoted text, lines with `Error|Exception|Traceback`), file hints (strings with `/` or known extensions), and keywords (stop-word-filtered nouns). Save to `investigations.extracted_terms`.
3. **GitHub issue input:** if `source_type=github_issue`, parse the URL (same strictness as repo URL, and the repo must match the analysed repository), fetch title/body/comments, build `issue_body`.
4. **Retrieval** (`investigate.py`): run keyword + symbol + semantic for each term group, fuse with RRF, apply boosts/penalties from `prd.md` §9.5, keep top 10 files / 20 chunks within `EVIDENCE_TOKEN_BUDGET` (estimate tokens ≈ chars/4). Assign each evidence item an ID `E1…En`. Compute `evidence_strength`.
5. Persist `investigation_results` **before** calling the LLM (so deterministic results survive an LLM failure).
6. **Reasoning step:** prompt per `prd.md` §9.6 with the numbered evidence; model returns JSON: `{why_relevant: {E#: text}, hypotheses: [{text, confidence, evidence_refs: [E#]}]}`.
7. **Validator** (`validator.py`): implement all five rules of `prd.md` §9.7 as pure functions with unit tests (invalid refs dropped, unsupported hypotheses flagged, paths verified, labels forced, disclaimer appended).
8. Endpoints: `POST /repositories/{id}/investigations` (202 + background task), `GET /investigations/{id}`, `GET /repositories/{id}/investigations`. Statuses move `pending → processing → ready|failed`. If the LLM fails, status is `ready` with `hypotheses=[]`, `llm_error` noted, and evidence still returned.
9. Also implement `POST /symbols/{id}/explain` (Module B) using the same service: input = symbol source + direct imports + up to 3 callers (found by symbol-name keyword search) → explanation labelled as hypothesis/AI interpretation.
10. Optional AI architecture summary (end of ingest, non-blocking): input = README excerpt + folder tree + frameworks + entry points + dependency hubs (top in-degree files); output labelled as AI interpretation.

**Gate:** Investigate a fixture issue → ranked files returned with evidence and line numbers; hypotheses only reference existing evidence IDs; disabling the LLM key still returns ranked evidence.

---

## 12. Phase 10 — Contribution Planner & Test Recommendations

**Files:** `services/planner.py`, `api/v1/plans.py`, `schemas/plan.py`, `prompts/plan.py`, `prompts/tests.py`.

**Tasks**
1. `PlannerService.create_plan(investigation_id, user_notes)`:
   - **Deterministic facts first:** candidate files = top investigation results; `impacted_files` = reverse dependencies (depth ≤ 2) of candidate files from `GraphService`; `existing tests` = mappings from `test_mappings` for candidate + impacted files.
   - **LLM step:** given issue, evidence, hypotheses, impacted files, existing tests, user notes → structured JSON (`summary`, `steps[]`, `risks[]`, `validation_checklist[]`, `recommended_tests[]`). Steps must reference only file paths from the provided candidate/impacted sets.
   - Run the **Validator**; assemble final plan per the schema in `prd.md` §8.7 including the constant disclaimer.
   - If the LLM fails: return a **deterministic fallback plan** (steps: "Read X", "Inspect Y", "Review impacted files…", "Run existing tests Z" marked `kind: "fact"` where derived from analysis) with `llm_error` noted.
2. Markdown renderer `render_plan_markdown(plan)`: sections with explicit tags `[Verified]` / `[Hypothesis]` next to each item, disclaimer at the end.
3. Endpoints: `POST /investigations/{id}/plan`, `GET /plans/{id}`, `GET /plans/{id}/export?format=markdown` (`Content-Disposition: attachment; filename=repopilot-plan.md`), `POST /investigations/{id}/test-recommendations`.

**Gate:** End-to-end via `curl`/pytest on the fixture repo: analyse → investigate → plan → export; Markdown contains the disclaimer and no sentence stating tests were run.

---

## 13. Frontend Phases (11–15)

### Phase 11 — Foundation
1. `npm create vite@latest frontend -- --template react-ts`; install: `tailwindcss postcss autoprefixer @tanstack/react-query zustand axios react-router-dom @xyflow/react dagre @types/dagre react-markdown shiki @tanstack/react-virtual clsx`; dev: `vitest @testing-library/react @testing-library/jest-dom jsdom`.
2. Implement `styles/tokens.css`, `neumorph.css`, `globals.css`, and `tailwind.config.ts` exactly per `design.md` §2 and §8. Load fonts (Barlow Semi Condensed, Figtree, JetBrains Mono) in `index.html`.
3. `api/client.ts`: Axios instance (`VITE_API_BASE_URL`), request interceptor adds `X-Session-Id` from `localStorage`; response interceptor stores the header if present and maps the error envelope to a typed `ApiError`.
4. `types/` mirroring backend schemas (write by hand from `prd.md` §8).
5. UI kit in `components/ui/` per `design.md` §8.3 (build `Button, Panel, Placard, Badge, Led, TextInput, TextArea, Switch, Segmented, CodeWindow, Toast, Skeleton, EmptyState, ErrorState, NeedleGauge, StageLamps, CounterDrum, EvidenceMeter, FileTree, StatWell, Tabs, Dialog`). Add a hidden `/styleguide` route that renders all of them in light and dark.
6. Layout: `TopBar`, `RepoShell` (left rail on desktop, bottom nav on mobile), theme toggle, `routes.tsx`.

**Gate:** `npm run build` passes with no TS errors; `/styleguide` shows every component; contrast spot-check passes in both themes.

### Phase 12 — Landing, Analysing, Overview
- **Landing:** URL input with validation LED (client regex mirroring the server's), primary key calls `POST /repositories`, navigates to `/repo/:id/analysing`. Show recent repositories. Static hero console demonstrating Verified vs Hypothesis.
- **Analysing (Cockpit):** poll `/repositories/:id/job` every 1.5 s with TanStack Query (`refetchInterval` until `ready|failed`); drive `NeedleGauge`, `StageLamps`, `CounterDrum`; handle `failed` with `ErrorState` (+ retry via reanalyse); auto-navigate on ready.
- **Overview:** stat wells, language bar, frameworks/entry points (Verified badges), architecture summary (Hypothesis badge), tree preview.

**Gate:** Paste a public repo URL in the browser → watch the cockpit → land on a populated Overview.

### Phase 13 — Explorer & Search
- Three-pane Explorer per `design.md` §4.4; `FileTree` lazy-loads via `/tree?path=` and is virtualised; `CodeWindow` renders content with Shiki, line numbers, and highlights from `?line=a-b`; outline from `/files/symbols`; "Explain" key calls explain endpoint with loading skeleton and Hypothesis badge.
- Search bar with `Segmented` mode selector; results as cards with glass snippet; click → opens file at line. Disable Semantic with tooltip when `semantic_available=false` (read from `/meta/capabilities` once and cache).
- Deep links: URL ↔ state sync (`/repo/:id/explorer?path=...&line=...`).

**Gate:** Search → click result → file opens scrolled to highlighted lines.

### Phase 14 — Dependencies
- Fetch `/graph`; lay out with `dagre` (rankdir LR); custom React Flow node types (`FileNode`, `FolderNode`); toolbar (level, include external, search node, re-layout); right drawer with node details and "Open in Explorer"; caption strip with static-extraction disclaimer; cycles flagged with red LED; mini-map and controls styled per `design.md` §3.11.
- Memoise nodes (`React.memo`), pass stable `nodeTypes`, and avoid inline object props to keep it smooth.

**Gate:** Graph renders for a ≥ 200-file repo without jank; folder collapse works.

### Phase 15 — Issues, Investigation, Plan, Tests
- **Issues:** composer with two tabs; submit → `POST /investigations` → navigate to detail; poll until `ready|failed`.
- **Investigation detail:** evidence strength meter; ranked cards with Verified/Hypothesis badges; hypotheses panel with confidence segments and clickable evidence refs; permanent disclaimer strip; "Generate contribution plan".
- **Plan:** checklist-style steps; sections per `design.md` §4.8; local-state validation checkboxes; "Copy Markdown" (clipboard) and "Download .md".
- **Tests page:** per `design.md` §4.9 with the permanent "does not run tests" notice.
- Global: every AI-authored string renders inside a component that **requires** a `kind` prop (`fact | hypothesis`) and shows the matching badge — make this a typed component (`<Statement kind="hypothesis">`) so it cannot be forgotten.

**Gate:** Full flow works in the browser: analyse → explore → graph → investigate → plan → export.

---

## 14. Phase 16 — Hardening

1. **Rate limiting** with `slowapi` per `prd.md` §8.9; return `RATE_LIMITED` envelope.
2. **Cleanup task:** an `asyncio` loop (every 30 min) deleting expired snapshots and repositories older than `DATA_RETENTION_HOURS`; unit-test with an artificially old row.
3. **Input limits:** issue body ≤ 20,000 chars; search query ≤ 500 chars; Pydantic `Field(max_length=…)`.
4. **Security review checklist:** CORS locked to `FRONTEND_ORIGIN`; no stack traces in responses; no secret values in logs; secret-flagged files return 404 from file endpoint; tar extraction hardened; subprocess args fixed; no `dangerouslySetInnerHTML`.
5. **Accessibility pass** per `design.md` §2.6 and §8.5 (keyboard path through Landing → Overview → Explorer; focus rings; reduced motion).
6. **Tests:** backend — URL parser, safe_extract (zip-slip archive fixture), secret scanner, parser/imports, graph (cycles), test mapping, RRF, validator, plan markdown; one integration test running the whole pipeline against a **mocked GitHub** (`respx`) serving a tiny tarball, and a **mocked LLM**. Frontend — `Badge`, `Statement`, URL validation, API client error mapping.
7. **Degradation matrix** (verify manually):
   | Condition | Expected behaviour |
   |---|---|
   | No `LLM_API_KEY` | Deterministic features work; AI endpoints return `LLM_UNAVAILABLE` or evidence-only results |
   | No pgvector / no embedding key | Hybrid → keyword + symbol; UI shows "Semantic search unavailable" |
   | Snapshot evicted | Keyword search falls back to Postgres FTS/trigram |
   | Tree-sitter parse error on a file | File still listed; symbols/imports empty; job continues |
   | GitHub rate limit | Clear `GITHUB_RATE_LIMIT` error suggesting a token |

**Gate:** `pytest` green; `npm run test` green; manual degradation matrix passes.

---

## 15. Phase 17 — Deployment & Docs

1. **Backend → Render:** Docker web service from `backend/`; add Postgres (enable `vector` if available); env vars from `prd.md` §11.1 with production values (`APP_ENV=production`, `FRONTEND_ORIGIN=<vercel url>`); health check path `/api/v1/health`.
2. **Frontend → Vercel:** root `frontend/`; `VITE_API_BASE_URL=<render url>/api/v1`; `vercel.json` with SPA rewrite `{ "source": "/(.*)", "destination": "/index.html" }` and security headers.
3. **README.md:** project description, architecture diagram (copy from `prd.md` §5.1), local setup (`docker compose up -d db`, backend and frontend commands), env variable table, limits, trust principles, known limitations, and the demo script below.
4. **Demo seed:** a script `scripts/demo.md` listing 2–3 small public repos and 2 sample issue texts that produce strong evidence — used for the hackathon demo.

**Demo script (3 minutes):** paste repo URL → cockpit analysis → Overview → search a symbol in Explorer → dependency graph → paste issue → show ranked evidence with Verified vs Hypothesis badges → generate plan → export Markdown → point to the "no code executed / tests not run" statements.

---

## 16. Cut-Line if Time Runs Short (Hackathon Priority)

**Never cut:** Phases 0–5, 9 (investigation + validator), 10 (plan), secret exclusion, Verified/Hypothesis badges, URL validation, safe extraction.

**Cut in this order (last first):**
1. Cycle detection and folder-level graph aggregation (keep a plain file graph).
2. Embeddings/semantic search (keep keyword + symbol; feature flag stays off).
3. AI architecture summary and "Explain symbol" (keep deterministic overview).
4. Test recommendations from the LLM (keep deterministic test mapping).
5. Dark theme (keep tokens structured so it can be added later).
6. Java/Go parsing (keep Python + JS/TS).

---

## 17. Common Pitfalls (Avoid)

- Running `alembic` migrations that require `vector` on a database without it — always guard.
- Sharing one DB session between the request and the background task — the task must create its own session.
- Blocking the event loop with CPU-heavy Tree-sitter parsing — run parsing in `asyncio.to_thread` (or a `ProcessPoolExecutor`) in batches.
- Holding giant repos in memory — stream, process file by file, batch inserts.
- Passing user input through a shell — always `create_subprocess_exec` with an argument list.
- Letting the LLM output file paths directly into the UI — they must pass through the validator.
- Using CORS `*` in production.
- Returning raw exceptions to the client.
- Forgetting `expose_headers=["X-Session-Id"]` in CORS, which breaks session persistence in the browser.
- Hard-coding colours in components instead of using tokens from `design.md`.
- Claiming anywhere in the UI or API that tests ran, passed, or were verified.

---

## 18. Final Definition of Done

Run through `prd.md` §16 (Acceptance Criteria) item by item. Additionally confirm:

- [ ] `git ls-files | grep -E "(^|/)\.env$"` returns nothing.
- [ ] A fresh clone follows the README and runs locally with only `docker compose up -d db`, two env files, and two start commands.
- [ ] The demo script runs end-to-end on the deployed URLs.
- [ ] Every AI-authored sentence in the UI is wrapped in a `Statement kind="hypothesis"` with an amber badge.
