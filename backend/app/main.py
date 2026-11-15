import asyncio
from contextlib import asynccontextmanager
import asyncpg
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1 import (
    explorer,
    graph,
    health,
    investigations,
    plans,
    repositories,
    search,
    tests,
)
from app.core.config import database_url_shape, settings
from app.core.errors import (
    AppError,
    app_error_handler,
    generic_exception_handler,
    http_exception_handler,
    validation_error_handler,
)
from app.core.logging import logger, setup_logging
from app.core.rate_limit import limiter, rate_limit_exceeded_handler
from app.db.session import dispose_engine, get_engine
from app.services.cleanup import cleanup_expired_snapshots_and_repos

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s v%s...", settings.APP_NAME, settings.APP_VERSION)
    semantic_enabled = False
    cleanup_task = None
    app.state.db = False
    app.state.migrated = False

    if not getattr(app.state, "testing", False):
        db_shape = database_url_shape(settings.DATABASE_URL)
        try:
            async def check_database():
                async with get_engine().connect() as conn:
                    await conn.execute(text("SELECT 1"))
                    migrated = (
                        await conn.execute(
                            text("SELECT to_regclass('public.repositories')")
                        )
                    ).scalar_one() is not None
                    vector = (
                        await conn.execute(
                            text(
                                "SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') "
                                "AND EXISTS (SELECT 1 FROM pg_attribute AS attribute "
                                "JOIN pg_class AS relation ON relation.oid = attribute.attrelid "
                                "JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace "
                                "WHERE namespace.nspname = 'public' AND relation.relname = 'code_chunks' "
                                "AND attribute.attname = 'embedding' AND NOT attribute.attisdropped)"
                            )
                        )
                    ).scalar_one()
                    return migrated, vector

            app.state.migrated, semantic_enabled = await asyncio.wait_for(
                check_database(), timeout=12
            )
            app.state.db = True
            if not app.state.migrated:
                logger.warning("Database is empty. Run: alembic upgrade head")
            elif semantic_enabled:
                logger.info("pgvector extension detected; semantic search is enabled.")
            else:
                logger.info(
                    "pgvector extension not found; falling back to FTS / trigram search."
                )
            if app.state.migrated:
                cleanup_task = asyncio.create_task(
                    cleanup_expired_snapshots_and_repos()
                )
        except (
            SQLAlchemyError,
            asyncpg.PostgresError,
            asyncio.TimeoutError,
            OSError,
        ):
            logger.warning(
                "Cannot connect to PostgreSQL at %s:%s/%s - check DATABASE_URL and that the server is running",
                db_shape["host"],
                db_shape["port"],
                db_shape["database"],
            )
    app.state.semantic_enabled = semantic_enabled

    yield

    logger.info("Shutting down %s...", settings.APP_NAME)
    if cleanup_task:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
    if not getattr(app.state, "testing", False):
        await dispose_engine()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Middleware
origins = [
    origin.strip().rstrip("/")
    for origin in settings.FRONTEND_ORIGIN.split(",")
    if origin.strip()
]
if settings.APP_ENV == "development":
    origins.extend(["http://localhost:5173", "http://127.0.0.1:5173"])
origins = list(dict.fromkeys(origins))

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["X-Session-Id", "Content-Type"],
    expose_headers=["X-Session-Id"],
)

# Exception handlers
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# Routers
app.include_router(health.router)  # /health and /meta/capabilities
prefix = settings.API_V1_PREFIX
app.include_router(health.router, prefix=prefix)
app.include_router(repositories.router, prefix=prefix)
app.include_router(explorer.router, prefix=prefix)
app.include_router(search.router, prefix=prefix)
app.include_router(graph.router, prefix=prefix)
app.include_router(investigations.router, prefix=prefix)
app.include_router(plans.router, prefix=prefix)
app.include_router(tests.router, prefix=prefix)
