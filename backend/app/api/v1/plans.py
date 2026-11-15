import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.config import settings
from app.core.rate_limit import limiter
from app.core.session import get_or_create_session_id
from app.db.models import ContributionPlan, Investigation
from app.db.session import get_db
from app.schemas.plan import CreatePlanRequest, PlanContent, PlanResponse
from app.services.planner import PlannerService
from app.services.validator import CONSTANT_DISCLAIMER

router = APIRouter(tags=["Contribution Plans"])


@router.post("/investigations/{inv_id}/plan", status_code=status.HTTP_201_CREATED, response_model=PlanResponse)
@limiter.limit(settings.RATE_LIMIT_LLM)
async def create_plan(
    request: Request,
    inv_id: uuid.UUID,
    req: CreatePlanRequest,
    session_id: uuid.UUID = Depends(get_or_create_session_id),
    db: AsyncSession = Depends(get_db),
):
    # Verify investigation access
    inv_stmt = select(Investigation).where(
        Investigation.id == inv_id,
        Investigation.session_id == session_id,
    )
    res = await db.execute(inv_stmt)
    inv = res.scalar_one_or_none()
    if not inv:
        raise AppError(code="NOT_FOUND", message="Investigation not found.", status_code=404)

    plan_record = await PlannerService.create_plan(
        db=db,
        investigation_id=inv_id,
        user_notes=req.user_notes,
    )

    return PlanResponse(
        id=plan_record.id,
        investigation_id=plan_record.investigation_id,
        user_notes=plan_record.user_notes,
        plan=PlanContent.model_validate(plan_record.plan),
        markdown=plan_record.markdown,
        created_at=plan_record.created_at,
        disclaimer=CONSTANT_DISCLAIMER,
    )


@router.get("/plans/{plan_id}", response_model=PlanResponse)
async def get_plan(
    plan_id: uuid.UUID,
    session_id: uuid.UUID = Depends(get_or_create_session_id),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(ContributionPlan)
        .join(Investigation, ContributionPlan.investigation_id == Investigation.id)
        .where(
            ContributionPlan.id == plan_id,
            Investigation.session_id == session_id,
        )
    )
    res = await db.execute(stmt)
    plan_record = res.scalar_one_or_none()
    if not plan_record:
        raise AppError(code="NOT_FOUND", message="Plan not found.", status_code=404)

    return PlanResponse(
        id=plan_record.id,
        investigation_id=plan_record.investigation_id,
        user_notes=plan_record.user_notes,
        plan=PlanContent.model_validate(plan_record.plan),
        markdown=plan_record.markdown,
        created_at=plan_record.created_at,
        disclaimer=CONSTANT_DISCLAIMER,
    )


@router.get("/plans/{plan_id}/export")
async def export_plan_markdown(
    plan_id: uuid.UUID,
    format: str = Query("markdown", pattern="^markdown$"),
    session_id: uuid.UUID = Depends(get_or_create_session_id),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(ContributionPlan)
        .join(Investigation, ContributionPlan.investigation_id == Investigation.id)
        .where(
            ContributionPlan.id == plan_id,
            Investigation.session_id == session_id,
        )
    )
    res = await db.execute(stmt)
    plan_record = res.scalar_one_or_none()
    if not plan_record:
        raise AppError(code="NOT_FOUND", message="Plan not found.", status_code=404)

    markdown_content = plan_record.markdown or "# Contribution Plan\n"
    return Response(
        content=markdown_content,
        media_type="text/markdown",
        headers={
            "Content-Disposition": 'attachment; filename="repopilot-plan.md"',
        },
    )
