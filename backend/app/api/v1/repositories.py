import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import AppError
from app.core.config import settings
from app.core.rate_limit import limiter
from app.core.security import parse_github_url
from app.core.session import get_or_create_session_id
from app.db.models import AnalysisJob, RepoFile, Repository, Symbol
from app.db.session import get_db
from app.schemas.repository import (
    AnalysisJobResponse,
    AnalyzeRepoRequest,
    AnalyzeRepoResponse,
    RepositoryOverview,
    RepositorySummary,
)
from app.services.github import GitHubService
from app.workers.jobs import launch_analysis_task

router = APIRouter(prefix="/repositories", tags=["Repositories"])


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=AnalyzeRepoResponse)
@limiter.limit(settings.RATE_LIMIT_ANALYSE)
async def analyze_repository(
    request: Request,
    req: AnalyzeRepoRequest,
    session_id: uuid.UUID = Depends(get_or_create_session_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        owner, repo_name, branch_from_url = parse_github_url(req.url)
    except AppError as exc:
        raise AppError(code="INVALID_ARGUMENT", message=exc.message, status_code=400) from exc
    target_branch = req.branch or branch_from_url

    # Fetch metadata synchronously from GitHub to fail fast
    gh = GitHubService()
    try:
        gh_data = await gh.get_repo(owner, repo_name)
        languages = await gh.get_languages(owner, repo_name)
    finally:
        await gh.close()

    branch = target_branch or gh_data.get("default_branch", "main")

    # Check for existing repo in this session
    existing_stmt = select(Repository).where(
        Repository.session_id == session_id,
        Repository.owner == owner,
        Repository.name == repo_name,
        Repository.branch == branch,
    )
    res = await db.execute(existing_stmt)
    existing_repo = res.scalar_one_or_none()

    if existing_repo:
        repo_obj = existing_repo
        repo_obj.description = gh_data.get("description")
        repo_obj.stars = gh_data.get("stargazers_count")
        repo_obj.license = gh_data.get("license", {}).get("spdx_id") if gh_data.get("license") else None
        repo_obj.topics = gh_data.get("topics", [])
        repo_obj.size_kb = gh_data.get("size")
        repo_obj.languages = languages
        repo_obj.status = "pending"
    else:
        repo_obj = Repository(
            session_id=session_id,
            owner=owner,
            name=repo_name,
            url=f"https://github.com/{owner}/{repo_name}",
            branch=branch,
            description=gh_data.get("description"),
            stars=gh_data.get("stargazers_count"),
            license=gh_data.get("license", {}).get("spdx_id") if gh_data.get("license") else None,
            topics=gh_data.get("topics", []),
            size_kb=gh_data.get("size"),
            languages=languages,
            status="pending",
        )
        db.add(repo_obj)
        await db.flush()

    # Create Analysis Job
    job = AnalysisJob(
        repository_id=repo_obj.id,
        stage="queued",
        progress=0,
        message="Job queued for analysis.",
    )
    db.add(job)
    await db.commit()
    await db.refresh(repo_obj)
    await db.refresh(job)

    # Launch background worker
    launch_analysis_task(repo_obj.id, job.id)

    return AnalyzeRepoResponse(
        repository_id=repo_obj.id,
        job_id=job.id,
        status="pending",
    )


@router.get("", response_model=List[RepositorySummary])
async def list_repositories(
    session_id: uuid.UUID = Depends(get_or_create_session_id),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Repository)
        .where(Repository.session_id == session_id)
        .order_by(Repository.created_at.desc())
    )
    res = await db.execute(stmt)
    return res.scalars().all()


@router.get("/{repo_id}", response_model=RepositoryOverview)
async def get_repository_overview(
    repo_id: uuid.UUID,
    session_id: uuid.UUID = Depends(get_or_create_session_id),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Repository).where(
        Repository.id == repo_id,
        Repository.session_id == session_id,
    )
    res = await db.execute(stmt)
    repo = res.scalar_one_or_none()
    if not repo:
        raise AppError(code="REPO_NOT_FOUND", message="Repository not found in your session.", status_code=404)

    # Compute summary stats
    file_count_res = await db.execute(
        select(func.count(RepoFile.id)).where(RepoFile.repository_id == repo_id)
    )
    symbol_count_res = await db.execute(
        select(func.count(Symbol.id)).where(Symbol.repository_id == repo_id)
    )
    test_count_res = await db.execute(
        select(func.count(RepoFile.id)).where(RepoFile.repository_id == repo_id, RepoFile.is_test == True)
    )

    overview = RepositoryOverview.model_validate(repo)
    overview.stats = {
        "files_count": file_count_res.scalar() or 0,
        "symbols_count": symbol_count_res.scalar() or 0,
        "tests_count": test_count_res.scalar() or 0,
        "languages_count": len(repo.languages) if repo.languages else 0,
    }
    return overview


@router.delete("/{repo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_repository(
    repo_id: uuid.UUID,
    session_id: uuid.UUID = Depends(get_or_create_session_id),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Repository).where(
        Repository.id == repo_id,
        Repository.session_id == session_id,
    )
    res = await db.execute(stmt)
    repo = res.scalar_one_or_none()
    if not repo:
        raise AppError(code="REPO_NOT_FOUND", message="Repository not found.", status_code=404)

    await db.delete(repo)
    await db.commit()
    return None


@router.get("/{repo_id}/job", response_model=AnalysisJobResponse)
async def get_latest_job(
    repo_id: uuid.UUID,
    session_id: uuid.UUID = Depends(get_or_create_session_id),
    db: AsyncSession = Depends(get_db),
):
    # Verify ownership
    repo_stmt = select(Repository.id).where(
        Repository.id == repo_id,
        Repository.session_id == session_id,
    )
    res_repo = await db.execute(repo_stmt)
    if not res_repo.scalar_one_or_none():
        raise AppError(code="REPO_NOT_FOUND", message="Repository not found.", status_code=404)

    job_stmt = (
        select(AnalysisJob)
        .where(AnalysisJob.repository_id == repo_id)
        .order_by(AnalysisJob.created_at.desc())
        .limit(1)
    )
    res_job = await db.execute(job_stmt)
    job = res_job.scalar_one_or_none()
    if not job:
        raise AppError(code="NOT_FOUND", message="No job found for this repository.", status_code=404)

    return job


@router.post("/{repo_id}/reanalyse", status_code=status.HTTP_202_ACCEPTED, response_model=AnalyzeRepoResponse)
async def reanalyse_repository(
    repo_id: uuid.UUID,
    session_id: uuid.UUID = Depends(get_or_create_session_id),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Repository).where(
        Repository.id == repo_id,
        Repository.session_id == session_id,
    )
    res = await db.execute(stmt)
    repo = res.scalar_one_or_none()
    if not repo:
        raise AppError(code="REPO_NOT_FOUND", message="Repository not found.", status_code=404)

    repo.status = "pending"
    job = AnalysisJob(
        repository_id=repo.id,
        stage="queued",
        progress=0,
        message="Re-analysis queued.",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    launch_analysis_task(repo.id, job.id)

    return AnalyzeRepoResponse(
        repository_id=repo.id,
        job_id=job.id,
        status="pending",
    )
