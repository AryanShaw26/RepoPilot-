import posixpath
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import AppError
from app.core.config import settings
from app.core.rate_limit import limiter
from app.core.session import get_or_create_session_id
from app.db.models import RepoFile, Repository, Symbol
from app.db.session import get_db
from app.prompts.explain_symbol import EXPLAIN_SYMBOL_SYSTEM, EXPLAIN_SYMBOL_USER
from app.schemas.repository import (
    ExplainSymbolResponse,
    FileContentResponse,
    SymbolItem,
    TreeNode,
)
from app.schemas.search import SearchResultItem
from app.services.graph import GraphService
from app.services.llm import LLMService
from app.services.search import search_symbols

router = APIRouter(prefix="/repositories/{repo_id}", tags=["Explorer"])


async def verify_repo_access(repo_id: uuid.UUID, session_id: uuid.UUID, db: AsyncSession) -> Repository:
    stmt = select(Repository).where(
        Repository.id == repo_id,
        Repository.session_id == session_id,
    )
    res = await db.execute(stmt)
    repo = res.scalar_one_or_none()
    if not repo:
        raise AppError(code="REPO_NOT_FOUND", message="Repository not found in your session.", status_code=404)
    return repo


@router.get("/tree", response_model=List[TreeNode])
async def get_tree(
    repo_id: uuid.UUID,
    path: str = Query("", description="Folder path inside repo"),
    session_id: uuid.UUID = Depends(get_or_create_session_id),
    db: AsyncSession = Depends(get_db),
):
    await verify_repo_access(repo_id, session_id, db)

    norm_path = path.strip("/").replace("\\", "/")

    # Fetch all files in the repo
    stmt = select(RepoFile).where(RepoFile.repository_id == repo_id)
    res = await db.execute(stmt)
    files = res.scalars().all()

    entries_map = {}

    for f in files:
        fpath = f.path.replace("\\", "/")
        if norm_path:
            if not fpath.startswith(norm_path + "/"):
                continue
            rel = fpath[len(norm_path) + 1 :]
        else:
            rel = fpath

        parts = rel.split("/")
        first_segment = parts[0]

        if len(parts) == 1:
            # File directly in current folder
            full_child_path = f"{norm_path}/{first_segment}".strip("/")
            entries_map[first_segment] = TreeNode(
                name=first_segment,
                path=full_child_path,
                type="file",
                size=f.size_bytes,
                language=f.language,
                is_test=f.is_test,
                is_entry_point=f.is_entry_point,
            )
        else:
            # Subdirectory
            full_child_path = f"{norm_path}/{first_segment}".strip("/")
            if first_segment not in entries_map:
                entries_map[first_segment] = TreeNode(
                    name=first_segment,
                    path=full_child_path,
                    type="directory",
                )

    # Sort: directories first, then alphabetical
    result = list(entries_map.values())
    result.sort(key=lambda x: (0 if x.type == "directory" else 1, x.name.lower()))
    return result


@router.get("/files", response_model=FileContentResponse)
async def get_file(
    repo_id: uuid.UUID,
    path: str = Query(..., description="File path relative to repo root"),
    session_id: uuid.UUID = Depends(get_or_create_session_id),
    db: AsyncSession = Depends(get_db),
):
    await verify_repo_access(repo_id, session_id, db)
    norm_path = path.strip("/").replace("\\", "/")

    stmt = select(RepoFile).where(
        RepoFile.repository_id == repo_id,
        RepoFile.path == norm_path,
    )
    res = await db.execute(stmt)
    f = res.scalar_one_or_none()
    if not f:
        raise AppError(code="NOT_FOUND", message=f"File '{norm_path}' not found.", status_code=404)

    if f.content is None and f.sha1 is not None:
        raise AppError(
            code="NOT_FOUND",
            message=f"File '{norm_path}' is classified as containing sensitive secrets or binary data and is redacted.",
            status_code=404,
        )

    return FileContentResponse(
        path=f.path,
        directory=f.directory,
        language=f.language,
        size_bytes=f.size_bytes,
        line_count=f.line_count,
        is_test=f.is_test,
        is_entry_point=f.is_entry_point,
        content=f.content or "",
    )


@router.get("/files/symbols", response_model=List[SymbolItem])
async def get_file_symbols(
    repo_id: uuid.UUID,
    path: str = Query(..., description="File path relative to repo root"),
    session_id: uuid.UUID = Depends(get_or_create_session_id),
    db: AsyncSession = Depends(get_db),
):
    await verify_repo_access(repo_id, session_id, db)
    norm_path = path.strip("/").replace("\\", "/")

    stmt = (
        select(Symbol, RepoFile.path)
        .join(RepoFile, Symbol.file_id == RepoFile.id)
        .where(
            Symbol.repository_id == repo_id,
            RepoFile.path == norm_path,
        )
        .order_by(Symbol.start_line)
    )
    res = await db.execute(stmt)
    symbols: List[SymbolItem] = []
    for s, fpath in res.all():
        symbols.append(
            SymbolItem(
                id=s.id,
                name=s.name,
                qualified_name=s.qualified_name,
                kind=s.kind,
                start_line=s.start_line,
                end_line=s.end_line,
                signature=s.signature,
                docstring=s.docstring,
                file_path=fpath,
            )
        )
    return symbols


@router.get("/symbols", response_model=List[SearchResultItem])
async def search_symbols_endpoint(
    repo_id: uuid.UUID,
    q: str = Query("", description="Symbol name query"),
    kind: Optional[str] = Query(None, description="Symbol kind filter"),
    limit: int = Query(20, ge=1, le=100),
    session_id: uuid.UUID = Depends(get_or_create_session_id),
    db: AsyncSession = Depends(get_db),
):
    await verify_repo_access(repo_id, session_id, db)
    return await search_symbols(db, repo_id, q, limit=limit, kind=kind)


@router.post("/symbols/{symbol_id}/explain", response_model=ExplainSymbolResponse)
@limiter.limit(settings.RATE_LIMIT_LLM)
async def explain_symbol(
    request: Request,
    repo_id: uuid.UUID,
    symbol_id: uuid.UUID,
    session_id: uuid.UUID = Depends(get_or_create_session_id),
    db: AsyncSession = Depends(get_db),
):
    await verify_repo_access(repo_id, session_id, db)

    # Fetch symbol and file
    stmt = (
        select(Symbol, RepoFile)
        .join(RepoFile, Symbol.file_id == RepoFile.id)
        .where(
            Symbol.id == symbol_id,
            Symbol.repository_id == repo_id,
        )
    )
    res = await db.execute(stmt)
    row = res.one_or_none()
    if not row:
        raise AppError(code="NOT_FOUND", message="Symbol not found.", status_code=404)

    symbol_obj, file_obj = row

    # Get lines of symbol
    snippet = ""
    if file_obj.content:
        lines = file_obj.content.splitlines()
        start = max(1, symbol_obj.start_line)
        end = min(len(lines), symbol_obj.end_line)
        snippet = "\n".join(lines[start - 1 : end])[:3000]

    # Get callers & imports
    deps = await GraphService.get_file_dependencies(db, repo_id, file_obj.path)
    imports_summary = "\n".join(f"- {imp.specifier}" for imp in deps.imports[:5]) or "None"
    callers_summary = "\n".join(f"- {c.target_path}" for c in deps.imported_by[:5]) or "None"

    # Call LLM
    try:
        llm = LLMService()
        user_prompt = EXPLAIN_SYMBOL_USER.format(
            symbol_name=symbol_obj.name,
            kind=symbol_obj.kind,
            file_path=file_obj.path,
            start_line=symbol_obj.start_line,
            end_line=symbol_obj.end_line,
            source_snippet=snippet or "(source unavailable)",
            imports_summary=imports_summary,
            callers_summary=callers_summary,
        )
        output = await llm.complete_json(
            system_prompt=EXPLAIN_SYMBOL_SYSTEM,
            user_prompt=user_prompt,
            schema_model=dict,
        )
        explanation = output.get("explanation", "Symbol analysis completed.")
        confidence = output.get("confidence", "medium")
    except Exception as e:
        explanation = (
            f"Symbol `{symbol_obj.name}` ({symbol_obj.kind}) defined in `{file_obj.path}` "
            f"lines {symbol_obj.start_line}-{symbol_obj.end_line}. (AI explanation currently unavailable: {e})"
        )
        confidence = "low"

    return ExplainSymbolResponse(
        explanation=explanation,
        kind="hypothesis",
        evidence=[
            {
                "file_path": file_obj.path,
                "start_line": symbol_obj.start_line,
                "end_line": symbol_obj.end_line,
                "snippet": snippet[:500],
            }
        ],
        callers=[c.model_dump() for c in deps.imported_by[:3]],
        imports=[imp.model_dump() for imp in deps.imports[:3]],
        confidence=confidence,
    )
