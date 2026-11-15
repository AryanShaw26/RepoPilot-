import asyncio
from typing import AsyncGenerator, Optional

import asyncpg
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import database_url_overridden, database_url_shape, settings
from app.core.errors import AppError
from app.core.logging import logger

engine: Optional[AsyncEngine] = None
AsyncSessionLocal = async_sessionmaker(
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


def get_engine() -> AsyncEngine:
    global engine
    if engine is None:
        engine = create_async_engine(
            settings.DATABASE_URL,
            echo=False,
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            pool_pre_ping=True,
            connect_args={"timeout": 10.0, "command_timeout": 30.0},
        )
        AsyncSessionLocal.configure(bind=engine)
        shape = database_url_shape(settings.DATABASE_URL)
        logger.info(
            "Database: driver=%s host=%s port=%s db=%s",
            shape["driver"],
            shape["host"],
            shape["port"],
            shape["database"],
        )
        if database_url_overridden():
            logger.warning(
                "OS DATABASE_URL overrides backend/.env; using the OS environment value."
            )
    return engine


async def dispose_engine() -> None:
    global engine
    if engine is not None:
        await engine.dispose()
        engine = None
        AsyncSessionLocal.configure(bind=None)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            await session.execute(text("SELECT 1"))
            yield session
        except (
            SQLAlchemyError,
            asyncpg.PostgresError,
            OSError,
            asyncio.TimeoutError,
        ) as exc:
            try:
                await session.rollback()
            except (SQLAlchemyError, asyncpg.PostgresError, OSError):
                pass
            logger.warning("Database request failed; returning DATABASE_UNAVAILABLE.")
            raise AppError(
                code="DATABASE_UNAVAILABLE",
                message="The database is unavailable. Check that PostgreSQL is running and migrations are applied.",
                status_code=503,
            ) from exc
        finally:
            await session.close()


def get_worker_session() -> AsyncSession:
    get_engine()
    return AsyncSessionLocal()
