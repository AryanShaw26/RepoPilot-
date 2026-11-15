import asyncio
import json
import os
import posixpath
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set
import uuid

from sqlalchemy import func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import logger
from app.db.models import CodeChunk, RepoFile, Symbol
from app.schemas.search import SearchFilters, SearchResultItem

_RIPGREP_UNAVAILABLE_LOGGED = False


def sanitize_query(query: str) -> str:
    cleaned = query.strip()[:500]
    return cleaned.replace("\x00", "")


async def search_symbols(
    db: AsyncSession,
    repository_id: uuid.UUID,
    query: str,
    limit: int = 20,
    kind: Optional[str] = None,
) -> List[SearchResultItem]:
    clean_q = sanitize_query(query)
    if not clean_q:
        return []

    stmt = (
        select(Symbol, RepoFile.path)
        .join(RepoFile, Symbol.file_id == RepoFile.id)
        .where(Symbol.repository_id == repository_id)
    )

    if kind:
        stmt = stmt.where(Symbol.kind == kind)

    # Search by ILIKE
    stmt = stmt.where(
        or_(
            Symbol.name.ilike(f"%{clean_q}%"),
            Symbol.qualified_name.ilike(f"%{clean_q}%"),
        )
    ).limit(limit)

    res = await db.execute(stmt)
    rows = res.all()

    results: List[SearchResultItem] = []
    for sym, file_path in rows:
        exact = sym.name.lower() == clean_q.lower()
        prefix = sym.name.lower().startswith(clean_q.lower())
        score = 1.0 if exact else (0.85 if prefix else 0.6)

        snippet = sym.signature or f"{sym.kind} {sym.name}"
        results.append(
            SearchResultItem(
                file_path=file_path,
                start_line=sym.start_line,
                end_line=sym.end_line,
                snippet=snippet,
                score=score,
                source=["symbol"],
                symbol_name=sym.name,
                kind=sym.kind,
            )
        )

    results.sort(key=lambda x: x.score, reverse=True)
    return results[:limit]


async def search_ripgrep(
    snapshot_dir: str,
    query: str,
    limit: int = 20,
    filters: Optional[SearchFilters] = None,
) -> List[SearchResultItem]:
    clean_q = sanitize_query(query)
    if not clean_q or not os.path.exists(snapshot_dir):
        return []

    cmd = [
        "rg",
        "--json",
        "--max-count",
        "5",
        "--max-filesize",
        "300K",
        "--glob",
        "!{.git,node_modules,dist,build,vendor}",
        "--ignore-case",
        "--fixed-strings",
    ]

    if filters and filters.language:
        cmd.extend(["--type", filters.language])

    cmd.extend(["--", clean_q, snapshot_dir])

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5.0)
    except FileNotFoundError:
        global _RIPGREP_UNAVAILABLE_LOGGED
        if not _RIPGREP_UNAVAILABLE_LOGGED:
            logger.warning(
                "ripgrep is unavailable; keyword search will use the PostgreSQL fallback."
            )
            _RIPGREP_UNAVAILABLE_LOGGED = True
        return []
    except asyncio.TimeoutError:
        logger.warning("ripgrep search timed out after 5s.")
        return []
    except Exception as e:
        logger.warning("ripgrep search failed: %s", e)
        return []

    results: List[SearchResultItem] = []
    lines_by_file: Dict[str, List[Dict[str, Any]]] = {}

    for line in stdout.decode("utf-8", errors="replace").splitlines():
        if not line:
            continue
        try:
            data = json.loads(line)
        except Exception:
            continue

        if data.get("type") == "match":
            payload = data.get("data", {})
            fpath_raw = payload.get("path", {}).get("text", "")
            rel_path = os.path.relpath(fpath_raw, snapshot_dir).replace("\\", "/")

            if filters and filters.path_prefix and not rel_path.startswith(filters.path_prefix):
                continue
            if filters and filters.exclude_tests and ("test" in rel_path.lower() or "spec" in rel_path.lower()):
                continue

            line_num = payload.get("line_number", 1)
            line_text = payload.get("lines", {}).get("text", "").strip()

            if rel_path not in lines_by_file:
                lines_by_file[rel_path] = []
            lines_by_file[rel_path].append({"line": line_num, "text": line_text})

    for rel_path, matches in lines_by_file.items():
        for m in matches[:3]:
            results.append(
                SearchResultItem(
                    file_path=rel_path,
                    start_line=m["line"],
                    end_line=m["line"],
                    snippet=m["text"],
                    score=0.8,
                    source=["keyword"],
                )
            )

    return results[:limit]


async def search_database_keyword(
    db: AsyncSession,
    repository_id: uuid.UUID,
    query: str,
    limit: int = 20,
    filters: Optional[SearchFilters] = None,
) -> List[SearchResultItem]:
    clean_q = sanitize_query(query)
    if not clean_q:
        return []

    stmt = (
        select(CodeChunk, RepoFile.path)
        .join(RepoFile, CodeChunk.file_id == RepoFile.id)
        .where(CodeChunk.repository_id == repository_id)
    )

    if filters and filters.language:
        stmt = stmt.where(RepoFile.language == filters.language)
    if filters and filters.path_prefix:
        stmt = stmt.where(RepoFile.path.startswith(filters.path_prefix))
    if filters and filters.exclude_tests:
        stmt = stmt.where(RepoFile.is_test == False)

    # Use ILIKE on chunk content as fallback
    stmt = stmt.where(CodeChunk.content.ilike(f"%{clean_q}%")).limit(limit)

    res = await db.execute(stmt)
    rows = res.all()

    results: List[SearchResultItem] = []
    for chunk, file_path in rows:
        chunk_lines = chunk.content.splitlines()
        matched_lines = [
            (i + 1, l) for i, l in enumerate(chunk_lines) if clean_q.lower() in l.lower()
        ]
        start_l = chunk.start_line
        end_l = chunk.end_line
        snippet = chunk.content[:300]
        if matched_lines:
            local_line, text = matched_lines[0]
            start_l = chunk.start_line + local_line - 1
            end_l = start_l
            snippet = text

        results.append(
            SearchResultItem(
                file_path=file_path,
                start_line=start_l,
                end_line=end_l,
                snippet=snippet,
                score=0.75,
                source=["keyword"],
            )
        )

    return results
