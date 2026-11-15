import asyncio
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import AppError
from app.core.config import settings
from app.core.rate_limit import limiter
from app.core.security import parse_github_issue_url
from app.core.session import get_or_create_session_id
from app.db.session import get_worker_session
from app.db.models import Investigation, InvestigationResult, RepoFile, Repository, Symbol
from app.db.session import get_db
from app.schemas.investigation import (
    CreateInvestigationRequest,
    EvidenceSnippet,
    Hypothesis,
    InvestigationResponse,
    IssueInfo,
    RankedResult,
    SymbolRef,
)
from app.services.github import GitHubService
from app.services.investigate import InvestigateService
from app.services.validator import CONSTANT_DISCLAIMER

router = APIRouter(tags=["Investigations"])
active_investigation_tasks = set()


async def _run_investigation_background(
    investigation_id: uuid.UUID,
    snapshot_dir: Optional[str],
) -> None:
    async with get_worker_session() as worker_db:
        await InvestigateService.run_investigation(
            db=worker_db,
            investigation_id=investigation_id,
            snapshot_dir=snapshot_dir,
        )


@router.post("/repositories/{repo_id}/investigations", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit(settings.RATE_LIMIT_LLM)
async def create_investigation(
    request: Request,
    repo_id: uuid.UUID,
    req: CreateInvestigationRequest,
    session_id: uuid.UUID = Depends(get_or_create_session_id),
    db: AsyncSession = Depends(get_db),
):
    # Verify repo
    stmt = select(Repository).where(
        Repository.id == repo_id,
        Repository.session_id == session_id,
    )
    res = await db.execute(stmt)
    repo = res.scalar_one_or_none()
    if not repo:
        raise AppError(code="REPO_NOT_FOUND", message="Repository not found.", status_code=404)

    title = req.issue_title
    body = req.issue_body or ""
    issue_url = req.issue_url

    if req.source_type == "github_issue":
        if not issue_url:
            raise AppError(code="INVALID_ARGUMENT", message="issue_url required for github_issue source_type.", status_code=400)
        try:
            owner, rname, issue_num = parse_github_issue_url(issue_url)
        except AppError as exc:
            raise AppError(code="INVALID_ARGUMENT", message=exc.message, status_code=400) from exc
        if owner.lower() != repo.owner.lower() or rname.lower() != repo.name.lower():
            raise AppError(
                code="INVALID_ARGUMENT",
                message=f"Issue URL must belong to repository {repo.owner}/{repo.name}.",
                status_code=400,
            )
        gh = GitHubService()
        try:
            gh_issue = await gh.get_issue(owner, rname, issue_num)
            title = gh_issue["title"]
            body = gh_issue["body"]
            if gh_issue.get("comments"):
                body += "\n\n### Issue Comments:\n" + "\n---\n".join(gh_issue["comments"])
        finally:
            await gh.close()

    inv = Investigation(
        repository_id=repo_id,
        session_id=session_id,
        source_type=req.source_type,
        issue_url=issue_url,
        issue_title=title,
        issue_body=body,
        status="pending",
    )
    db.add(inv)
    await db.commit()
    await db.refresh(inv)

    # Launch background task
    task = asyncio.create_task(
        _run_investigation_background(inv.id, repo.snapshot_path)
    )
    active_investigation_tasks.add(task)
    task.add_done_callback(active_investigation_tasks.discard)

    return {"investigation_id": inv.id, "status": "pending"}


@router.get("/investigations/{inv_id}", response_model=InvestigationResponse)
async def get_investigation(
    inv_id: uuid.UUID,
    session_id: uuid.UUID = Depends(get_or_create_session_id),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Investigation)
        .options(
            selectinload(Investigation.results).selectinload(InvestigationResult.file),
            selectinload(Investigation.results).selectinload(InvestigationResult.symbol),
        )
        .where(
            Investigation.id == inv_id,
            Investigation.session_id == session_id,
        )
    )
    res = await db.execute(stmt)
    inv = res.scalar_one_or_none()
    if not inv:
        raise AppError(code="NOT_FOUND", message="Investigation not found.", status_code=404)

    results_dto: List[RankedResult] = []
    for r in inv.results:
        fpath = r.file.path if r.file else "unknown"
        sref = None
        if r.symbol:
            sref = SymbolRef(
                name=r.symbol.name,
                kind=r.symbol.kind,
                start_line=r.symbol.start_line,
                end_line=r.symbol.end_line,
            )
        why_rel_dict = {"text": r.why_relevant or "", "kind": "hypothesis"}
        evidence_snippets = [
            EvidenceSnippet(
                start_line=ev.get("start_line", 1),
                end_line=ev.get("end_line", 1),
                snippet=ev.get("snippet", ""),
            )
            for ev in (r.evidence or [])
        ]
        results_dto.append(
            RankedResult(
                rank=r.rank,
                file_path=fpath,
                symbol=sref,
                score=r.score,
                retrieval_sources=r.retrieval_sources,
                why_relevant=why_rel_dict,
                evidence=evidence_snippets,
            )
        )

    hypotheses_dto = [
        Hypothesis(
            id=h.get("id", "h"),
            text=h.get("text", ""),
            kind="hypothesis",
            confidence=h.get("confidence", "medium"),
            evidence_refs=h.get("evidence_refs", []),
            unsupported=h.get("unsupported", False),
        )
        for h in (inv.hypotheses or [])
    ]

    return InvestigationResponse(
        id=inv.id,
        status=inv.status,
        issue=IssueInfo(
            title=inv.issue_title,
            body=inv.issue_body,
            url=inv.issue_url,
        ),
        extracted_terms=inv.extracted_terms or {},
        evidence_strength=inv.evidence_strength or "moderate",
        results=results_dto,
        hypotheses=hypotheses_dto,
        disclaimer=CONSTANT_DISCLAIMER,
        error=inv.error,
        created_at=inv.created_at,
    )


@router.get("/repositories/{repo_id}/investigations")
async def list_repo_investigations(
    repo_id: uuid.UUID,
    session_id: uuid.UUID = Depends(get_or_create_session_id),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Investigation.id, Investigation.issue_title, Investigation.status, Investigation.created_at)
        .where(
            Investigation.repository_id == repo_id,
            Investigation.session_id == session_id,
        )
        .order_by(Investigation.created_at.desc())
    )
    res = await db.execute(stmt)
    return [
        {"id": row[0], "title": row[1] or "Untitled", "status": row[2], "created_at": row[3]}
        for row in res.all()
    ]
