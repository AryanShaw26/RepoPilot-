import uuid
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.session import get_or_create_session_id
from app.db.models import Repository
from app.db.session import get_db
from app.schemas.search import SearchRequest, SearchResponse, SearchResultItem
from app.services.retrieval import RetrievalService
from app.services.search import (
    search_database_keyword,
    search_ripgrep,
    search_symbols,
)

router = APIRouter(prefix="/repositories/{repo_id}", tags=["Search"])


@router.post("/search", response_model=SearchResponse)
async def search_repository(
    repo_id: uuid.UUID,
    req: SearchRequest,
    session_id: uuid.UUID = Depends(get_or_create_session_id),
    db: AsyncSession = Depends(get_db),
):
    # Verify repo access
    stmt = select(Repository).where(
        Repository.id == repo_id,
        Repository.session_id == session_id,
    )
    res = await db.execute(stmt)
    repo = res.scalar_one_or_none()
    if not repo:
        raise AppError(code="REPO_NOT_FOUND", message="Repository not found.", status_code=404)

    mode = req.mode.lower()

    if mode == "keyword":
        results = []
        if repo.snapshot_path:
            results = await search_ripgrep(repo.snapshot_path, req.query, limit=req.limit, filters=req.filters)
        if not results:
            results = await search_database_keyword(db, repo_id, req.query, limit=req.limit, filters=req.filters)
        semantic_available = await RetrievalService.semantic_storage_available(db)
        return SearchResponse(results=results, semantic_available=semantic_available)

    elif mode == "symbol":
        results = await search_symbols(db, repo_id, req.query, limit=req.limit)
        semantic_available = await RetrievalService.semantic_storage_available(db)
        return SearchResponse(results=results, semantic_available=semantic_available)

    else:
        # semantic or hybrid mode
        results, sem_avail = await RetrievalService.hybrid_search(
            db=db,
            repository_id=repo_id,
            query=req.query,
            snapshot_dir=repo.snapshot_path,
            limit=req.limit,
            filters=req.filters,
        )
        return SearchResponse(results=results, semantic_available=sem_avail)
