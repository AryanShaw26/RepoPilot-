import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.session import get_or_create_session_id
from app.db.models import Repository
from app.db.session import get_db
from app.schemas.graph import FileDependenciesResponse, GraphResponse
from app.services.graph import GraphService

router = APIRouter(prefix="/repositories/{repo_id}", tags=["Dependency Graph"])


async def verify_repo_access(repo_id: uuid.UUID, session_id: uuid.UUID, db: AsyncSession):
    stmt = select(Repository.id).where(
        Repository.id == repo_id,
        Repository.session_id == session_id,
    )
    res = await db.execute(stmt)
    if not res.scalar_one_or_none():
        raise AppError(code="REPO_NOT_FOUND", message="Repository not found.", status_code=404)


@router.get("/graph", response_model=GraphResponse)
async def get_dependency_graph(
    repo_id: uuid.UUID,
    level: str = Query("file", pattern="^(file|folder)$"),
    path_prefix: Optional[str] = Query(None),
    include_external: bool = Query(False),
    session_id: uuid.UUID = Depends(get_or_create_session_id),
    db: AsyncSession = Depends(get_db),
):
    await verify_repo_access(repo_id, session_id, db)
    return await GraphService.build_graph(
        db=db,
        repository_id=repo_id,
        level=level,
        path_prefix=path_prefix,
        include_external=include_external,
    )


@router.get("/files/dependencies", response_model=FileDependenciesResponse)
async def get_file_dependencies_endpoint(
    repo_id: uuid.UUID,
    path: str = Query(..., description="File path"),
    session_id: uuid.UUID = Depends(get_or_create_session_id),
    db: AsyncSession = Depends(get_db),
):
    await verify_repo_access(repo_id, session_id, db)
    norm_path = path.strip("/").replace("\\", "/")
    return await GraphService.get_file_dependencies(db, repo_id, norm_path)
