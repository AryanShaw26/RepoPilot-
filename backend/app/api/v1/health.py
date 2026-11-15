import asyncio
import asyncpg
from fastapi import APIRouter, Request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.db.session import get_engine
from app.schemas.common import CapabilitiesResponse, HealthResponse

router = APIRouter(tags=["Health & Meta"])
SUPPORTED_LLM_PROVIDERS = {"anthropic", "openai"}


def _llm_available() -> bool:
    return bool(settings.LLM_API_KEY) and settings.LLM_PROVIDER.lower() in SUPPORTED_LLM_PROVIDERS


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request):
    db_ok = False
    migrated = False
    semantic_enabled = (
        getattr(request.app.state, "semantic_enabled", False)
        and settings.FEATURE_SEMANTIC_SEARCH
        and bool(settings.EMBEDDING_API_KEY)
    )
    if getattr(request.app.state, "testing", False):
        db_ok = getattr(request.app.state, "db", False)
        migrated = getattr(request.app.state, "migrated", False)
    else:
        try:
            async def check_database():
                async with get_engine().connect() as conn:
                    await conn.execute(text("SELECT 1"))
                    return (
                        await conn.execute(
                            text("SELECT to_regclass('public.repositories')")
                        )
                    ).scalar_one() is not None

            migrated = await asyncio.wait_for(check_database(), timeout=12)
            db_ok = True
        except (
            SQLAlchemyError,
            asyncpg.PostgresError,
            asyncio.TimeoutError,
            OSError,
        ):
            db_ok = False
            migrated = False

    return HealthResponse(
        status="ok" if db_ok and migrated else "degraded",
        db=db_ok,
        migrated=migrated,
        semantic_enabled=semantic_enabled,
        llm_configured=bool(settings.LLM_API_KEY),
        github_token_configured=bool(settings.GITHUB_TOKEN),
        version=settings.APP_VERSION,
    )


@router.get("/meta/capabilities", response_model=CapabilitiesResponse)
async def get_capabilities(request: Request):
    semantic_enabled = (
        getattr(request.app.state, "semantic_enabled", False)
        and settings.FEATURE_SEMANTIC_SEARCH
        and bool(settings.EMBEDDING_API_KEY)
    )

    return CapabilitiesResponse(
        semantic_search=semantic_enabled and bool(settings.EMBEDDING_API_KEY),
        llm_available=_llm_available(),
        llm_provider=settings.LLM_PROVIDER,
        embedding_provider=settings.EMBEDDING_PROVIDER,
        max_repo_size_mb=settings.MAX_REPO_SIZE_MB,
        max_files=settings.MAX_FILES,
        max_file_bytes=settings.MAX_FILE_BYTES,
    )
