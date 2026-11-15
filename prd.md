# RepoPilot — Product Requirements Document (PRD)

> **Team CodeBeaver · Hackathon 2026 · Version 1.0**
> **Audience:** AI coding agent and human developers. This document is the single source of truth for *what* to build. See `design.md` for *how it looks* and `implementation_guide.md` for *the order of building*.

---

## 0. How to Read This Document (Agent Instructions)

- Everything marked **MUST** is required for the MVP. **SHOULD** is desirable if time permits. **MAY** is optional.
- Never invent endpoints, tables, or env variables that conflict with this document. If something is unspecified, choose the simplest option consistent with the principles in Section 2.
- The product's core rule: **facts come from deterministic analysis; the LLM only interprets retrieved evidence, and every AI statement is labelled as a hypothesis.** Violating this rule is a critical bug.
- Do not execute any code from analysed repositories. Ever.

---

## 1. Product Overview

**Name:** RepoPilot
**Tagline:** Understand the code. Contribute with confidence.
**One-liner:** An AI-powered repository intelligence and contribution assistant that analyses a public GitHub repository, maps its code relationships, and uses retrieved evidence to help developers investigate an issue and plan their next contribution.

### 1.1 Problem

When developers enter an unfamiliar repository, the context needed to contribute safely is scattered across source code, configuration, dependencies, issues, and tests. Code search finds matching text but does not explain the code, rank evidence, or suggest a safe sequence of changes.

Four pain points:
1. **Slow onboarding** — manually tracing folders, entry points, configs, modules.
2. **Scattered context** — architecture, dependencies, and test knowledge live in different places.
3. **Weak issue triage** — search returns matches, not the strongest evidence or why it matters.
4. **Unclear next steps** — no reliable sequence of changes, checks, and tests.

### 1.2 Solution

One connected workflow:

```
GitHub repository → code intelligence → issue investigation → contribution plan
```

A **hybrid pipeline**: deterministic analysis (Tree-sitter, ripgrep, GitHub API) establishes *what is in the code*; the LLM explains *what the evidence may mean*.

### 1.3 Target Users

| Persona | Need |
|---|---|
| First-time open-source contributor | Know where to start in an unfamiliar repo |
| Student / junior developer | Understand architecture and module relationships quickly |
| Maintainer / reviewer | Triage an issue to relevant files and tests fast |

### 1.4 Goals (MVP)

1. Accept a public GitHub repo URL and produce a structured analysis within a reasonable time (target: < 90 s for repos up to ~2,000 source files).
2. Let the user explore files, symbols, and imports, and search code with keyword + semantic search.
3. Let the user paste an issue (text or GitHub issue URL) and receive ranked relevant files/functions with evidence snippets and line references.
4. Generate a contribution plan: ordered steps, impacted files, risks, and test recommendations — with facts and hypotheses visibly separated.
5. Visualise statically extracted module dependencies as an interactive graph.

### 1.5 Non-Goals (MVP)

- No private repositories (public first). No GitHub OAuth in MVP.
- No code execution, test execution, or build of the analysed repo.
- No automatic PR creation or code modification.
- No claim that tests passed/failed. RepoPilot only *recommends* tests.
- No multi-user accounts/auth in MVP (sessions are anonymous; see §10).

---

## 2. Guiding Principles (Trust & Reliability)

| # | Principle | Enforcement in code |
|---|---|---|
| P1 | **Facts first** | File paths, symbols, imports, snippets, and line numbers are produced only by the analysis layer (Tree-sitter/ripgrep/GitHub API), never by the LLM. |
| P2 | **Traceable answers** | Every finding in an API response carries an `evidence[]` array: `{file_path, start_line, end_line, snippet, source}`. |
| P3 | **Hypotheses, not certainty** | Every LLM-derived claim has `kind: "hypothesis"` and a `confidence` of `low|medium|high`. UI shows a "Hypothesis — verify before implementing" badge. |
| P4 | **Safe by default** | Read-only analysis; no execution of repo code; secrets excluded from indexing; size/time limits; SSRF-safe URL validation. |
| P5 | **Disclose uncertainty** | If evidence is weak, the response says so (`evidence_strength: "weak"`). The assistant never says a test ran unless it actually ran (it never does in MVP). |
| P6 | **Validation step** | A post-LLM validator drops/flags any file path or line range in the LLM output that does not exist in the indexed evidence set. |

---

## 3. Feature Specification (Six Modules)

### 3.1 Module A — Repository Intelligence
**MUST**
- Parse GitHub URL (`https://github.com/{owner}/{repo}`, optional `/tree/{branch}`), validate, resolve default branch and commit SHA.
- Fetch repo metadata (description, stars, topics, license, default branch, size, languages) via GitHub REST API.
- Download the repo snapshot as a tarball (no `git clone`, no hooks), extract to a temp dir, enforce limits (§9.3).
- Detect: languages (by extension + GitHub languages API), frameworks (via manifest files: `package.json`, `requirements.txt`, `pyproject.toml`, `pom.xml`, `go.mod`, `Cargo.toml`), entry points (heuristics: `main.py`, `app.py`, `index.js`, `server.ts`, `src/main.*`, `package.json#main/scripts.start`, `Dockerfile CMD`), directory structure tree.
- Output a **Repository Overview**: summary stats, language breakdown, detected frameworks, entry points, folder tree, README excerpt, and an optional LLM-written "architecture summary" labelled as AI interpretation.

### 3.2 Module B — Codebase Explorer
**MUST**
- File tree browser with language icon and size.
- File viewer with syntax highlighting and line numbers; deep-link to line ranges (`?line=40-72`).
- Symbol outline per file (functions, classes, methods) from Tree-sitter with line ranges.
- "Explain this symbol" — LLM explanation grounded in the symbol's source + its direct imports/callers (retrieved), labelled as AI interpretation.
- Code search: keyword (ripgrep), symbol (DB lookup), semantic (embeddings) with a combined mode.

### 3.3 Module C — Dependency Mapper
**MUST**
- Statically extract import/require/from-import statements per file (Tree-sitter queries) and resolve to internal files where possible; external packages grouped as "external".
- Build a graph: nodes = files (or folders when collapsed), edges = imports.
- Render with React Flow; support collapse by folder, search/highlight node, click to open file.
- Show metrics: in-degree (most depended-on), out-degree, detected cycles (SHOULD).
- Label clearly: "Statically extracted imports — dynamic imports/reflection may be missing."

### 3.4 Module D — Issue Intelligence
**MUST**
- Input: free-text issue description OR GitHub issue URL (fetch title/body/labels/comments via GitHub API).
- Pipeline: extract keywords, identifiers, error strings, file hints → hybrid retrieval (keyword + symbol + semantic) → rerank → top-N files/functions with evidence snippets.
- Output: ranked list with `score`, `why_relevant` (short; AI-labelled), `evidence[]`, and `evidence_strength`.
- LLM produces **potential causes** as hypotheses only, citing evidence indices.

### 3.5 Module E — Contribution Planner
**MUST**
- Input: an investigation (Module D result), optionally user notes ("I want to fix X in Y way").
- Output (structured JSON, rendered as UI):
  - `summary` (hypothesis-labelled)
  - `steps[]` — ordered; each has `title`, `description`, `files[]`, `kind: "fact"|"hypothesis"`
  - `impacted_files[]` — from dependency graph (reverse dependencies of changed files = *facts*)
  - `risks[]` — each labelled hypothesis, with rationale
  - `validation_checklist[]` — manual checks
  - `disclaimer` — constant string (see §3.7)
- Export plan as Markdown (download/copy).

### 3.6 Module F — Test Intelligence
**MUST**
- Detect test files and frameworks by convention (`test_*.py`, `*_test.go`, `*.spec.ts`, `__tests__/`, `tests/`, pytest/jest/vitest/junit markers).
- Map source files → likely test files (name proximity + import analysis = *facts*).
- Recommend test scenarios and edge cases for an investigation (LLM; hypotheses).
- **Never** report that tests were run or passed.

### 3.7 Constant Disclaimer (include in every plan/investigation response)
`"AI-generated suggestions are hypotheses based on retrieved repository evidence. Verify before implementing. RepoPilot did not execute any code or tests."`

---

## 4. User Flows

1. **Analyse:** Landing → paste GitHub URL → click "Analyse repository" → progress screen (stages: Fetching → Parsing → Indexing → Embedding → Ready) → Overview dashboard.
2. **Explore:** Overview → Explorer (file tree + viewer + outline) → search.
3. **Map:** Overview → Dependencies graph → click node → open in Explorer.
4. **Investigate:** Issues tab → paste issue or URL → ranked evidence + hypotheses.
5. **Plan:** From an investigation → "Generate contribution plan" → plan view → export Markdown.
6. **Tests:** Plan/Investigation → "Test recommendations" panel.

---

## 5. System Architecture

### 5.1 High-Level Diagram

```
┌──────────────────────────┐        HTTPS/JSON        ┌────────────────────────────────────────────┐
│  Frontend (Vercel)       │ ───────────────────────► │  Backend API (Render) — FastAPI            │
│  React + TS + Tailwind   │ ◄─────────────────────── │                                            │
│  React Flow, Axios       │      polling / SSE       │  ┌──────────┐  ┌──────────────────────┐    │
└──────────────────────────┘                          │  │ Routers  │→ │ Services             │    │
                                                      │  └──────────┘  │  - GitHubService     │    │
                                                      │                │  - IngestService     │    │
                                                      │                │  - ParserService (TS)│    │
                                                      │                │  - SearchService     │    │
                                                      │                │  - GraphService      │    │
                                                      │                │  - LLMService        │    │
                                                      │                │  - InvestigateService│    │
                                                      │                │  - PlannerService    │    │
                                                      │                │  - TestIntelService  │    │
                                                      │                │  - ValidatorService  │    │
                                                      │                └──────────┬───────────┘    │
                                                      │   Background worker (asyncio task pool)    │
                                                      └─────────┬──────────────┬───────────────────┘
                                                                │              │
                                              ┌─────────────────▼───┐   ┌──────▼─────────────┐
                                              │ PostgreSQL          │   │ External APIs      │
                                              │ (+ pgvector, FTS)   │   │ GitHub REST, LLM,  │
                                              └─────────────────────┘   │ Embeddings         │
                                                                        └────────────────────┘
        Ephemeral temp storage (tarball extract) ── deleted after indexing
```

### 5.2 Components

| Component | Responsibility |
|---|---|
| **Frontend SPA** | UI, routing, state, graph rendering, polling job status |
| **API layer (FastAPI)** | Validation (Pydantic), routing, error mapping, rate limiting |
| **Ingest pipeline** | Download tarball → extract → filter → parse → chunk → embed → persist |
| **Parser service** | Tree-sitter parsing for symbols/imports (Python, JS/TS, Java, Go minimum) |
| **Search service** | Ripgrep (live keyword over the stored snapshot), Postgres FTS, symbol lookup, pgvector semantic search, score fusion |
| **LLM service** | Provider-agnostic wrapper (completion + embeddings), structured JSON output, retries, token budgeting |
| **Validator** | Verifies LLM-referenced paths/lines against evidence; strips unsupported claims |
| **Job runner** | In-process async background tasks; job state persisted in Postgres (no Redis needed for MVP) |

### 5.3 Intelligence Pipeline (Four Stages)

1. **STRUCTURE** — languages, entry points, symbols, imports, test locations (deterministic).
2. **RETRIEVAL** — combine keyword (ripgrep/FTS) + symbol + semantic (pgvector) results; fuse with Reciprocal Rank Fusion (RRF, k=60).
3. **REASONING** — LLM receives *only* the retrieved evidence (numbered), the issue text, and strict instructions; returns JSON with hypotheses referencing evidence IDs.
4. **VALIDATION** — Validator checks every referenced file/line, ensures facts vs hypotheses labels, adds `evidence_strength`, returns the structured result.

### 5.4 Snapshot Storage Strategy

- Ripgrep needs files on disk. For MVP: extract the tarball to `SNAPSHOT_DIR/{repo_id}/` and **keep it** until TTL expiry (default 24 h) so keyword search works; a cleanup task deletes expired snapshots.
- File contents are also stored in the DB (`repo_files.content`, text files ≤ `MAX_FILE_BYTES`) so the app still works if the snapshot is evicted (Render free-tier disks are ephemeral). If the snapshot is missing, ripgrep falls back to Postgres FTS + `pg_trgm` ILIKE.

### 5.5 Embeddings Fallback

- If `pgvector` extension is available → semantic search enabled (`FEATURE_SEMANTIC_SEARCH=true`).
- If not → system auto-degrades to FTS + trigram + symbol search; the UI shows a "Semantic search unavailable" notice. Never crash.

---

## 6. Technology Stack

| Layer | Technology | Notes |
|---|---|---|
| Frontend | React 18, TypeScript, Vite | SPA |
| Styling | Tailwind CSS + custom CSS variables | Skeuomorphic/neumorphic tokens (see `design.md`) |
| Graph | React Flow (`@xyflow/react`) + `dagre` for layout | Dependency map |
| State/data | TanStack Query, Zustand (light UI state) | Polling & caching |
| HTTP | Axios | Single client with interceptors |
| Code view | `react-syntax-highlighter` or `shiki` | Syntax highlight |
| Markdown | `react-markdown` | Plan rendering/export |
| Backend | Python 3.11+, FastAPI, Uvicorn | Async |
| Validation | Pydantic v2, pydantic-settings | Schemas & env |
| DB access | SQLAlchemy 2.0 (async) + asyncpg, Alembic | Migrations |
| Code analysis | `tree-sitter` + `tree-sitter-languages` (or per-language grammars), ripgrep (`rg` binary) | |
| GitHub | GitHub REST API via `httpx` | Tarball + metadata + issues |
| AI | LLM API (configurable provider) + Embeddings API | `LLM_PROVIDER`, `LLM_MODEL`, `EMBEDDING_MODEL` |
| Database | PostgreSQL 15+ with `pgvector`, `pg_trgm` | Fallback without pgvector |
| Rate limiting | `slowapi` | Per-IP |
| Logging | `structlog` or stdlib logging (JSON) | |
| Testing | pytest, httpx AsyncClient; Vitest + React Testing Library | |
| Deployment | Vercel (frontend), Render (backend + Postgres) | Dockerfile for backend |
| VCS | Git + GitHub | |

---

## 7. Database Design (PostgreSQL)

### 7.1 Extensions

```sql
CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS vector;       -- optional: wrap in DO block, ignore failure
```

### 7.2 Entity-Relationship Overview

```
sessions 1─* repositories 1─* repo_files 1─* symbols
                │                 │
                │                 ├─* code_chunks (with embedding)
                │                 └─* file_imports (edges)
                ├─* analysis_jobs
                ├─* investigations 1─* investigation_results
                │          └─* contribution_plans
                └─* test_mappings
```

### 7.3 Schema (SQL)

```sql
-- Anonymous client sessions (MVP: no login)
CREATE TABLE sessions (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE repositories (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID REFERENCES sessions(id) ON DELETE CASCADE,
    owner           TEXT NOT NULL,
    name            TEXT NOT NULL,
    url             TEXT NOT NULL,
    branch          TEXT NOT NULL,
    commit_sha      TEXT,
    description     TEXT,
    stars           INTEGER,
    license         TEXT,
    topics          TEXT[] DEFAULT '{}',
    size_kb         INTEGER,
    languages       JSONB DEFAULT '{}'::jsonb,        -- {"Python": 61234, ...} bytes
    frameworks      JSONB DEFAULT '[]'::jsonb,        -- [{"name":"FastAPI","evidence":"requirements.txt"}]
    entry_points    JSONB DEFAULT '[]'::jsonb,        -- [{"path":"app/main.py","reason":"..."}]
    readme_excerpt  TEXT,
    architecture_summary TEXT,                         -- AI-labelled
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','processing','ready','failed')),
    snapshot_path   TEXT,
    snapshot_expires_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (session_id, owner, name, commit_sha)
);
CREATE INDEX idx_repositories_session ON repositories(session_id);

CREATE TABLE analysis_jobs (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repository_id UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    stage        TEXT NOT NULL DEFAULT 'queued'
                 CHECK (stage IN ('queued','fetching','parsing','indexing','embedding','ready','failed')),
    progress     SMALLINT NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 100),
    message      TEXT,
    error        TEXT,
    started_at   TIMESTAMPTZ,
    finished_at  TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_jobs_repo ON analysis_jobs(repository_id);

CREATE TABLE repo_files (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repository_id UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    path          TEXT NOT NULL,
    directory     TEXT NOT NULL,
    language      TEXT,
    size_bytes    INTEGER NOT NULL,
    line_count    INTEGER,
    is_test       BOOLEAN NOT NULL DEFAULT false,
    is_entry_point BOOLEAN NOT NULL DEFAULT false,
    content       TEXT,                                 -- NULL if binary/too large
    content_tsv   TSVECTOR,
    sha1          TEXT,
    UNIQUE (repository_id, path)
);
CREATE INDEX idx_files_repo ON repo_files(repository_id);
CREATE INDEX idx_files_tsv ON repo_files USING GIN (content_tsv);
CREATE INDEX idx_files_path_trgm ON repo_files USING GIN (path gin_trgm_ops);

CREATE TABLE symbols (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repository_id UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    file_id       UUID NOT NULL REFERENCES repo_files(id) ON DELETE CASCADE,
    name          TEXT NOT NULL,
    qualified_name TEXT,
    kind          TEXT NOT NULL CHECK (kind IN ('function','class','method','interface','type','variable','enum')),
    start_line    INTEGER NOT NULL,
    end_line      INTEGER NOT NULL,
    signature     TEXT,
    docstring     TEXT,
    parent_symbol_id UUID REFERENCES symbols(id) ON DELETE CASCADE
);
CREATE INDEX idx_symbols_repo_name ON symbols(repository_id, name);
CREATE INDEX idx_symbols_name_trgm ON symbols USING GIN (name gin_trgm_ops);
CREATE INDEX idx_symbols_file ON symbols(file_id);

-- Import edges (statically extracted)
CREATE TABLE file_imports (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repository_id UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    source_file_id UUID NOT NULL REFERENCES repo_files(id) ON DELETE CASCADE,
    target_file_id UUID REFERENCES repo_files(id) ON DELETE SET NULL,  -- NULL if external/unresolved
    raw_specifier TEXT NOT NULL,          -- e.g. "./utils", "fastapi", "app.core.config"
    is_external   BOOLEAN NOT NULL DEFAULT false,
    package_name  TEXT,                   -- for externals
    line          INTEGER
);
CREATE INDEX idx_imports_repo ON file_imports(repository_id);
CREATE INDEX idx_imports_source ON file_imports(source_file_id);
CREATE INDEX idx_imports_target ON file_imports(target_file_id);

-- Chunks for retrieval. embedding column only if pgvector exists.
CREATE TABLE code_chunks (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repository_id UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    file_id       UUID NOT NULL REFERENCES repo_files(id) ON DELETE CASCADE,
    symbol_id     UUID REFERENCES symbols(id) ON DELETE SET NULL,
    start_line    INTEGER NOT NULL,
    end_line      INTEGER NOT NULL,
    content       TEXT NOT NULL,
    token_estimate INTEGER,
    content_tsv   TSVECTOR
    -- embedding vector(1536)   -- added by migration if pgvector available
);
CREATE INDEX idx_chunks_repo ON code_chunks(repository_id);
CREATE INDEX idx_chunks_tsv ON code_chunks USING GIN (content_tsv);
-- If pgvector:
-- ALTER TABLE code_chunks ADD COLUMN embedding vector(1536);
-- CREATE INDEX idx_chunks_embedding ON code_chunks USING hnsw (embedding vector_cosine_ops);

CREATE TABLE test_mappings (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repository_id  UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    source_file_id UUID NOT NULL REFERENCES repo_files(id) ON DELETE CASCADE,
    test_file_id   UUID NOT NULL REFERENCES repo_files(id) ON DELETE CASCADE,
    method         TEXT NOT NULL CHECK (method IN ('name_convention','import_analysis','directory_proximity')),
    confidence     TEXT NOT NULL CHECK (confidence IN ('low','medium','high')),
    UNIQUE (source_file_id, test_file_id)
);

CREATE TABLE investigations (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repository_id UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    session_id    UUID REFERENCES sessions(id) ON DELETE CASCADE,
    source_type   TEXT NOT NULL CHECK (source_type IN ('text','github_issue')),
    issue_url     TEXT,
    issue_title   TEXT,
    issue_body    TEXT NOT NULL,
    extracted_terms JSONB DEFAULT '{}'::jsonb,   -- keywords, identifiers, error strings
    status        TEXT NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending','processing','ready','failed')),
    evidence_strength TEXT CHECK (evidence_strength IN ('weak','moderate','strong')),
    hypotheses    JSONB DEFAULT '[]'::jsonb,
    error         TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_investigations_repo ON investigations(repository_id);

CREATE TABLE investigation_results (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    investigation_id UUID NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    rank             INTEGER NOT NULL,
    file_id          UUID REFERENCES repo_files(id) ON DELETE SET NULL,
    symbol_id        UUID REFERENCES symbols(id) ON DELETE SET NULL,
    score            REAL NOT NULL,
    retrieval_sources TEXT[] NOT NULL,           -- {'keyword','symbol','semantic'}
    why_relevant     TEXT,                       -- AI-labelled
    evidence         JSONB NOT NULL DEFAULT '[]'::jsonb   -- [{start_line,end_line,snippet}]
);
CREATE INDEX idx_inv_results_inv ON investigation_results(investigation_id, rank);

CREATE TABLE contribution_plans (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    investigation_id UUID NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    user_notes       TEXT,
    plan             JSONB NOT NULL,   -- structured plan (see §8.7)
    markdown         TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 7.4 Migrations

- Use **Alembic**. Migration `0001_init` creates everything above except the `embedding` column.
- Migration `0002_pgvector` runs in a `try/except`: if `CREATE EXTENSION vector` succeeds, add `embedding vector(EMBEDDING_DIM)` + HNSW index; otherwise skip and log a warning.
- On startup the app checks `SELECT 1 FROM pg_extension WHERE extname='vector'` and sets runtime flag `semantic_enabled`.

### 7.5 Retention

- Background task purges repositories (and cascaded data) older than `DATA_RETENTION_HOURS` (default 72) and deletes expired snapshot dirs.

---

## 8. API Specification

**Base URL:** `/api/v1` · **Format:** JSON · **Auth:** anonymous session via header `X-Session-Id` (UUID). If absent, the server creates a session and returns it in the response header `X-Session-Id`; the frontend stores it in `localStorage`.

**Standard error envelope**

```json
{ "error": { "code": "REPO_TOO_LARGE", "message": "Repository exceeds the 150 MB limit.", "details": {} } }
```

Error codes: `INVALID_URL`, `INVALID_ARGUMENT`, `DATABASE_UNAVAILABLE`, `REPO_NOT_FOUND`, `REPO_PRIVATE`, `REPO_TOO_LARGE`, `RATE_LIMITED`, `GITHUB_RATE_LIMIT`, `ANALYSIS_NOT_READY`, `NOT_FOUND`, `LLM_UNAVAILABLE`, `VALIDATION_ERROR`, `INTERNAL_ERROR`.

### 8.1 Health & Meta

| Method | Path | Description |
|---|---|---|
| GET | `/health` | `{status:"ok", db:true, semantic_enabled:bool, version}` |
| GET | `/meta/capabilities` | Feature flags: semantic search, LLM provider available, limits |

### 8.2 Repositories

| Method | Path | Description |
|---|---|---|
| POST | `/repositories` | Start analysis. Body: `{ "url": "https://github.com/owner/repo", "branch": "main"? }` → `202 { repository_id, job_id, status }` |
| GET | `/repositories` | List current session's repos |
| GET | `/repositories/{repo_id}` | Overview (metadata, languages, frameworks, entry points, readme excerpt, architecture summary, stats) |
| DELETE | `/repositories/{repo_id}` | Delete repo + all data |
| GET | `/repositories/{repo_id}/job` | Latest job: `{stage, progress, message, error}` (frontend polls every 1.5 s) |
| POST | `/repositories/{repo_id}/reanalyse` | Re-run analysis |

### 8.3 Explorer

| Method | Path | Description |
|---|---|---|
| GET | `/repositories/{repo_id}/tree?path=` | Directory listing (children: name, type, size, language) |
| GET | `/repositories/{repo_id}/files?path=...` | File content + metadata + language + line_count |
| GET | `/repositories/{repo_id}/files/symbols?path=...` | Symbol outline for a file |
| POST | `/repositories/{repo_id}/symbols/{symbol_id}/explain` | AI explanation `{explanation, kind:"hypothesis", evidence[], callers[], imports[]}` |
| GET | `/repositories/{repo_id}/symbols?q=&kind=&limit=` | Symbol search |

### 8.4 Search

| Method | Path | Description |
|---|---|---|
| POST | `/repositories/{repo_id}/search` | Body: `{ "query": "...", "mode": "keyword|symbol|semantic|hybrid", "limit": 20, "filters": {"language":"python","path_prefix":"src/","exclude_tests":false} }` → `{results:[{file_path, start_line, end_line, snippet, score, source[]}], semantic_available:bool}` |

### 8.5 Dependencies

| Method | Path | Description |
|---|---|---|
| GET | `/repositories/{repo_id}/graph?level=file|folder&path_prefix=&include_external=false` | `{nodes:[{id,label,path,language,in_degree,out_degree,type}], edges:[{id,source,target,kind}], stats:{...}, cycles:[[...]]}` |
| GET | `/repositories/{repo_id}/files/dependencies?path=` | `{imports:[...], imported_by:[...]}` for one file |

### 8.6 Investigations (Issue Intelligence)

| Method | Path | Description |
|---|---|---|
| POST | `/repositories/{repo_id}/investigations` | Body: `{ "source_type":"text","issue_body":"...", "issue_title":"..." }` **or** `{ "source_type":"github_issue","issue_url":"https://github.com/o/r/issues/12" }` → `202 {investigation_id}` |
| GET | `/investigations/{inv_id}` | Full result (see below) |
| GET | `/repositories/{repo_id}/investigations` | History |

**Investigation response**

```json
{
  "id": "uuid",
  "status": "ready",
  "issue": { "title": "...", "body": "...", "url": null },
  "extracted_terms": { "keywords": [], "identifiers": [], "error_strings": [], "file_hints": [] },
  "evidence_strength": "moderate",
  "results": [
    {
      "rank": 1,
      "file_path": "app/auth/session.py",
      "symbol": { "name": "refresh_token", "kind": "function", "start_line": 40, "end_line": 88 },
      "score": 0.83,
      "retrieval_sources": ["keyword", "semantic"],
      "why_relevant": { "text": "...", "kind": "hypothesis" },
      "evidence": [{ "start_line": 52, "end_line": 61, "snippet": "..." }]
    }
  ],
  "hypotheses": [
    { "id": "h1", "text": "...", "kind": "hypothesis", "confidence": "medium", "evidence_refs": ["1:52-61"] }
  ],
  "disclaimer": "AI-generated suggestions are hypotheses ..."
}
```

### 8.7 Contribution Plans

| Method | Path | Description |
|---|---|---|
| POST | `/investigations/{inv_id}/plan` | Body: `{ "user_notes": "optional" }` → `201 plan` |
| GET | `/plans/{plan_id}` | Plan JSON |
| GET | `/plans/{plan_id}/export?format=markdown` | `text/markdown` download |

**Plan JSON**

```json
{
  "id": "uuid",
  "summary": { "text": "...", "kind": "hypothesis" },
  "steps": [
    { "order": 1, "title": "Reproduce locally", "description": "...", "files": ["app/auth/session.py"], "kind": "hypothesis" }
  ],
  "impacted_files": [
    { "path": "app/api/routes.py", "reason": "imports app/auth/session.py", "kind": "fact" }
  ],
  "risks": [ { "text": "...", "kind": "hypothesis", "confidence": "low" } ],
  "validation_checklist": [ "Run the existing auth tests", "Manually verify ..." ],
  "tests": {
    "existing": [ { "path": "tests/test_session.py", "method": "name_convention", "confidence": "high", "kind": "fact" } ],
    "recommended": [ { "scenario": "Expired token during refresh", "kind": "hypothesis" } ]
  },
  "disclaimer": "AI-generated suggestions are hypotheses ... RepoPilot did not execute any code or tests."
}
```

### 8.8 Test Intelligence

| Method | Path | Description |
|---|---|---|
| GET | `/repositories/{repo_id}/tests` | Detected test files, frameworks, and coverage-proxy stats (`% of source files with ≥1 mapped test`) |
| GET | `/repositories/{repo_id}/tests/for?path=` | Tests mapped to a source file |
| POST | `/investigations/{inv_id}/test-recommendations` | `{existing:[...facts], recommended:[...hypotheses], edge_cases:[...]}` |

### 8.9 Rate Limits

- `POST /repositories`: 5 / hour / IP.
- LLM-backed endpoints (`explain`, `investigations`, `plan`, `test-recommendations`): 30 / hour / IP.
- All others: 120 / minute / IP.

---

## 9. Processing Details

### 9.1 Ingest Pipeline Stages (job `stage` values)

1. `fetching` (0–20 %) — GitHub metadata; download tarball (`GET /repos/{o}/{r}/tarball/{ref}`, follow redirects, stream to disk, enforce size).
2. `parsing` (20–50 %) — walk files, apply ignore rules, language detection, Tree-sitter symbols + imports.
3. `indexing` (50–75 %) — persist files/symbols/imports, build FTS vectors, resolve imports to files, detect tests + mappings, detect frameworks/entry points.
4. `embedding` (75–98 %) — chunk by symbol (fallback: 60-line windows with 10-line overlap), batch-embed (batch size 64), store vectors. Skipped if semantic disabled.
5. `ready` (100 %) — optionally generate AI architecture summary (non-blocking; failure must not fail the job).

### 9.2 Indexing Exclusions (Secrets & Noise)

Never index these paths/patterns (case-insensitive):
`.env`, `.env.*`, `*.pem`, `*.key`, `*.p12`, `*.pfx`, `id_rsa*`, `*.crt` (private), `secrets.*`, `credentials*`, `*.keystore`, `.git/`, `node_modules/`, `vendor/`, `dist/`, `build/`, `.next/`, `__pycache__/`, `*.min.js`, `*.lock` (except noted for framework detection only), images/binaries/archives, files > `MAX_FILE_BYTES`.

Additionally run a lightweight **secret scanner** (regex for AWS keys, GitHub tokens `ghp_`, `sk-`, private key headers). A file with a hit is stored **without content** (`content = NULL`) and flagged; matched strings are never sent to the LLM or returned by the API.

### 9.3 Limits

| Limit | Default |
|---|---|
| `MAX_REPO_SIZE_MB` (tarball) | 150 |
| `MAX_FILES` | 5,000 indexed files |
| `MAX_FILE_BYTES` | 300,000 |
| `MAX_CHUNKS_PER_REPO` | 20,000 |
| Analysis timeout | 300 s |
| LLM context budget per request | ≤ 12,000 tokens of evidence |

### 9.4 URL Validation (SSRF & Abuse Protection)

- Only `https://github.com/{owner}/{repo}` hosts accepted. Regex-validate owner/repo (`^[A-Za-z0-9_.-]{1,100}$`). Reject anything else. Backend only calls `api.github.com`.

### 9.5 Retrieval Fusion

For an issue: build queries from `keywords`, `identifiers`, `error_strings`; run keyword (FTS/ripgrep), symbol, semantic; fuse via RRF; boost files whose path matches `file_hints`; downweight tests and vendored files unless the issue mentions tests; take top 10 files / 20 chunks; assign `evidence_strength`:
- `strong`: ≥3 results scoring above threshold from ≥2 retrieval sources including an exact identifier/error-string match
- `moderate`: results from ≥2 sources or one exact match
- `weak`: otherwise (UI must show a visible "weak evidence" warning)

### 9.6 LLM Prompting Contract

- System prompt must include: *"You may only reference evidence items provided, by their IDs. Never invent files, functions, or line numbers. Label all conclusions as hypotheses with a confidence level. If evidence is insufficient, say so. Never claim code or tests were run."*
- Output: **JSON only**, validated against a Pydantic model; on parse failure retry once with a repair prompt; on second failure return `LLM_UNAVAILABLE` with the raw deterministic evidence still included (graceful degradation).
- Temperature ≤ 0.2.

### 9.7 Validator Rules

1. Every `evidence_refs` ID must exist in the supplied evidence set, otherwise drop that reference.
2. Hypotheses with zero valid refs are downgraded to `confidence: "low"` and flagged `unsupported: true`.
3. Any file path mentioned in `steps[].files` must exist in `repo_files`; otherwise removed.
4. Force `kind: "hypothesis"` on all LLM-authored text; only analysis-derived items may be `kind: "fact"`.
5. Append the constant disclaimer.

---

## 10. Security & Privacy

- **Read-only analysis**; no `git clone` hooks, no `exec`, no `subprocess` on repo files except `rg` with fixed args and a `--` terminator; user queries passed as arguments (never via shell), with `--max-count`, `--max-filesize`, and a timeout.
- Safe tar extraction: reject absolute paths, `..`, symlinks, and device files (zip-slip protection).
- CORS: allow only `FRONTEND_ORIGIN`.
- Input size limits: issue body ≤ 20,000 chars; search query ≤ 500 chars.
- No secrets in logs; mask tokens.
- Anonymous sessions; data auto-purged (§7.5). Sessions scope all reads (a repo not owned by the session returns 404).
- Security headers on frontend (Vercel `vercel.json`): `X-Content-Type-Options`, `Referrer-Policy`, CSP.
- Render untrusted code snippets as text only (never `dangerouslySetInnerHTML`).
- Dependency pinning via lockfiles.

---

## 11. Environment Configuration

### 11.1 Backend `.env.example` (commit this; never commit `.env`)

```dotenv
# ---------- App ----------
APP_ENV=development                 # development | production
APP_NAME=RepoPilot
APP_VERSION=1.0.0
LOG_LEVEL=INFO
API_V1_PREFIX=/api/v1
FRONTEND_ORIGIN=http://localhost:5173

# ---------- Database (PostgreSQL) ----------
DATABASE_URL=postgresql+asyncpg://repopilot:change_me@localhost:5432/repopilot
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=10

# ---------- GitHub ----------
GITHUB_TOKEN=                       # fine-grained PAT, public-repo read only; raises rate limit
GITHUB_API_BASE=https://api.github.com
GITHUB_REQUEST_TIMEOUT_S=30

# ---------- LLM & Embeddings ----------
LLM_PROVIDER=anthropic              # anthropic | openai | gemini
LLM_API_KEY=
LLM_MODEL=                          # set to a current model id from your provider
LLM_MAX_OUTPUT_TOKENS=2000
LLM_TEMPERATURE=0.2
EMBEDDING_PROVIDER=openai           # openai | gemini
EMBEDDING_API_KEY=
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIM=1536

# ---------- Feature Flags ----------
FEATURE_SEMANTIC_SEARCH=true        # auto-disabled if pgvector missing
FEATURE_AI_ARCH_SUMMARY=true

# ---------- Limits ----------
MAX_REPO_SIZE_MB=150
MAX_FILES=5000
MAX_FILE_BYTES=300000
MAX_CHUNKS_PER_REPO=20000
ANALYSIS_TIMEOUT_S=300
EVIDENCE_TOKEN_BUDGET=12000

# ---------- Storage & Retention ----------
SNAPSHOT_DIR=./.data/snapshots
SNAPSHOT_TTL_HOURS=24
DATA_RETENTION_HOURS=72

# ---------- Rate Limiting ----------
RATE_LIMIT_ANALYSE=5/hour
RATE_LIMIT_LLM=30/hour
RATE_LIMIT_DEFAULT=120/minute
```

Supported LLM providers are `anthropic`, `openai`, and `gemini`; supported embedding
providers are `openai` and `gemini`. Gemini uses the configured `LLM_API_KEY` and
`LLM_MODEL`, requests JSON MIME output, and sends responses through the same schema
validator and one repair attempt (§9.6). Gemini embeddings use `EMBEDDING_API_KEY`,
`EMBEDDING_MODEL`, and `EMBEDDING_DIM` as the requested output dimensionality.
Unsupported providers disable the relevant capability with a clear reason and make
no provider requests. Provider HTTP retries are limited to 429/5xx, with at most two
retries; 4xx responses are never retried.

### 11.2 Frontend `.env.example`

```dotenv
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_APP_NAME=RepoPilot
```

> Only variables prefixed `VITE_` are exposed to the browser. **Never** put API keys in the frontend env.

### 11.3 Config Loader Requirements

- Use `pydantic-settings` `BaseSettings`; fail fast at startup if required vars (`DATABASE_URL`) are missing; warn (not crash) if `LLM_API_KEY` is missing — the app must still run deterministic features and disable AI endpoints with a clear `LLM_UNAVAILABLE` response.

---

## 12. `.gitignore` (root of monorepo)

```gitignore
# ===== Secrets & environment (CRITICAL) =====
.env
.env.*
!.env.example
*.pem
*.key
*.p12
*.pfx
secrets/
credentials*.json
service-account*.json

# ===== Python =====
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/

# ===== Node / Frontend =====
node_modules/
dist/
build/
.vite/
.vercel/
*.tsbuildinfo
coverage/

# ===== App data (snapshots of analysed repos, local DB dumps) =====
.data/
snapshots/
*.sqlite
*.dump
*.sql.bak
pgdata/

# ===== Logs =====
*.log
logs/

# ===== OS / Editor =====
.DS_Store
Thumbs.db
.idea/
.vscode/*
!.vscode/extensions.json

# ===== Docker =====
docker-compose.override.yml
```

---

## 13. Repository Structure (Monorepo)

```
repopilot/
├── README.md
├── prd.md  design.md  implementation_guide.md
├── .gitignore
├── docker-compose.yml                 # postgres(pgvector) + backend + frontend for local dev
├── backend/
│   ├── Dockerfile                     # installs ripgrep
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── .env.example
│   ├── alembic/versions/
│   ├── app/
│   │   ├── main.py                    # FastAPI app factory, CORS, routers, lifespan
│   │   ├── core/        (config.py, logging.py, security.py, errors.py, rate_limit.py)
│   │   ├── db/          (session.py, models.py, base.py)
│   │   ├── schemas/     (repository.py, search.py, graph.py, investigation.py, plan.py, common.py)
│   │   ├── api/v1/      (health.py, repositories.py, explorer.py, search.py, graph.py,
│   │   │                 investigations.py, plans.py, tests.py)
│   │   ├── services/    (github.py, ingest.py, parser.py, languages.py, imports.py,
│   │   │                 secrets.py, search.py, retrieval.py, embeddings.py, llm.py,
│   │   │                 graph.py, investigate.py, planner.py, test_intel.py,
│   │   │                 validator.py, cleanup.py)
│   │   ├── prompts/     (explain_symbol.py, investigate.py, plan.py, tests.py, arch_summary.py)
│   │   └── workers/     (jobs.py)
│   └── tests/           (unit + integration; fixtures with a tiny sample repo)
└── frontend/
    ├── package.json  vite.config.ts  tailwind.config.ts  tsconfig.json  vercel.json
    ├── .env.example
    └── src/
        ├── main.tsx  App.tsx  routes.tsx
        ├── api/         (client.ts, repositories.ts, search.ts, graph.ts, investigations.ts, plans.ts)
        ├── styles/      (tokens.css, neumorph.css, globals.css)
        ├── components/  (ui/*, layout/*, explorer/*, graph/*, issue/*, plan/*, common/*)
        ├── pages/       (Landing, Analysing, Overview, Explorer, Dependencies, Issues,
        │                 InvestigationDetail, Plan, Tests, NotFound)
        ├── hooks/  lib/  store/  types/
        └── tests/
```

---

## 14. Non-Functional Requirements

| Area | Requirement |
|---|---|
| Performance | Overview loads < 1 s after analysis; search < 800 ms (hybrid); graph render for ≤ 500 visible nodes smooth (use folder collapse beyond that) |
| Reliability | Job failures surface a readable error; partial results never presented as complete; LLM failure degrades to deterministic evidence |
| Observability | Structured logs with `job_id`, `repository_id`; `/health` endpoint |
| Accessibility | Keyboard navigation, visible focus rings, WCAG AA contrast, reduced-motion support (see `design.md`) |
| Responsiveness | Fully usable ≥ 360 px width; Explorer collapses to tabs on mobile |
| Browser support | Latest Chrome, Firefox, Safari, Edge |
| Testing | Backend unit tests for parser, import resolver, validator, URL validator, secret scanner; one end-to-end test on a small fixture repo |

---

## 15. Deployment

- **Backend (Render):** Docker web service; build installs `ripgrep`; start: `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`; managed Postgres (enable `vector` if offered). Set env vars in the dashboard.
- **Frontend (Vercel):** Vite build; set `VITE_API_BASE_URL` to the Render URL; SPA fallback rewrite to `/index.html` in `vercel.json`.
- **Local:** `docker-compose up` (Postgres with pgvector image `pgvector/pgvector:pg16`), backend on `:8000`, frontend on `:5173`.

---

## 16. Acceptance Criteria (MVP "Done" Checklist)

- [ ] Pasting a valid public GitHub URL starts analysis and shows staged progress; invalid/private/oversized repos show clear errors.
- [ ] Overview shows languages, frameworks, entry points, folder tree, README excerpt.
- [ ] Explorer lists files, opens a file with highlighting, shows a symbol outline, supports deep-linked line ranges.
- [ ] Keyword, symbol, and (if available) semantic/hybrid search return results with snippets and line references.
- [ ] Dependency graph renders, supports folder collapse, node click opens the file, and displays the static-extraction disclaimer.
- [ ] Issue investigation (text and GitHub URL) returns ranked files with evidence snippets, `evidence_strength`, and hypotheses labelled as such.
- [ ] Contribution plan returns ordered steps, impacted files (facts from reverse dependencies), risks, validation checklist, tests; exports to Markdown.
- [ ] Test intelligence lists detected tests, maps source → tests, and **never** claims tests ran.
- [ ] Every AI output carries a visible "Hypothesis" badge; facts carry a "Verified from source" badge.
- [ ] Secrets are excluded from indexing; `.env` and keys never appear in any API response.
- [ ] App runs with no LLM key (deterministic features work) and without pgvector (fallback search works).
- [ ] `.env` is git-ignored; `.env.example` files committed.

---

## 17. Future Scope (Out of MVP)

Private repos via GitHub OAuth, PR draft generation, multi-language call-graph depth, repo comparison, saved workspaces with accounts, VS Code extension, GitHub App for auto-triage.
