import uuid
from typing import List
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.config import settings
from app.core.rate_limit import limiter
from app.core.session import get_or_create_session_id
from app.db.models import Investigation, RepoFile, Repository
from app.db.session import get_db
from app.prompts.tests import TESTS_SYSTEM, TESTS_USER
from app.schemas.plan import (
    ExistingTest,
    RecommendedTest,
    TestIntelOverview,
    TestRecommendations,
)
from app.services.llm import LLMService
from app.services.test_intel import TestIntelService
from app.services.validator import validate_recommended_tests

router = APIRouter(tags=["Test Intelligence"])


@router.get("/repositories/{repo_id}/tests", response_model=TestIntelOverview)
async def get_repository_tests_overview(
    repo_id: uuid.UUID,
    session_id: uuid.UUID = Depends(get_or_create_session_id),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Repository.id).where(
        Repository.id == repo_id,
        Repository.session_id == session_id,
    )
    res = await db.execute(stmt)
    if not res.scalar_one_or_none():
        raise AppError(code="REPO_NOT_FOUND", message="Repository not found.", status_code=404)

    return await TestIntelService.get_test_intel_overview(db, repo_id)


@router.get("/repositories/{repo_id}/tests/for", response_model=List[ExistingTest])
async def get_tests_for_file_endpoint(
    repo_id: uuid.UUID,
    path: str = Query(..., description="Source file path"),
    session_id: uuid.UUID = Depends(get_or_create_session_id),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Repository.id).where(
        Repository.id == repo_id,
        Repository.session_id == session_id,
    )
    res = await db.execute(stmt)
    if not res.scalar_one_or_none():
        raise AppError(code="REPO_NOT_FOUND", message="Repository not found.", status_code=404)

    norm_path = path.strip("/").replace("\\", "/")
    return await TestIntelService.get_tests_for_file(db, repo_id, norm_path)


@router.post("/investigations/{inv_id}/test-recommendations", response_model=TestRecommendations)
@limiter.limit(settings.RATE_LIMIT_LLM)
async def get_investigation_test_recommendations(
    request: Request,
    inv_id: uuid.UUID,
    session_id: uuid.UUID = Depends(get_or_create_session_id),
    db: AsyncSession = Depends(get_db),
):
    inv_stmt = select(Investigation).where(
        Investigation.id == inv_id,
        Investigation.session_id == session_id,
    )
    res = await db.execute(inv_stmt)
    inv = res.scalar_one_or_none()
    if not inv:
        raise AppError(code="NOT_FOUND", message="Investigation not found.", status_code=404)

    # Gather existing tests
    existing_tests: List[ExistingTest] = []
    # Try LLM recommendations
    recommended_list: List[RecommendedTest] = []
    try:
        llm = LLMService()
        user_prompt = TESTS_USER.format(
            issue_body=inv.issue_body,
            findings=str(inv.hypotheses),
        )
        llm_out = await llm.complete_json(
            system_prompt=TESTS_SYSTEM,
            user_prompt=user_prompt,
            schema_model=dict,
        )
        rec_raw = llm_out.get("recommended", [])
        validated = validate_recommended_tests(rec_raw)
        recommended_list = [RecommendedTest.model_validate(t) for t in validated]
    except Exception:
        recommended_list = [
            RecommendedTest(scenario="Verify input edge cases and error handling", kind="hypothesis"),
            RecommendedTest(scenario="Verify regression test coverage for modified symbols", kind="hypothesis"),
        ]

    return TestRecommendations(
        existing=existing_tests,
        recommended=recommended_list,
    )
