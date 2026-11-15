import asyncio
import os
import shutil
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.logging import logger
from app.db.models import Repository
from app.db.session import get_worker_session


async def cleanup_expired_snapshots_and_repos():
    """
    Periodically checks for expired snapshots on disk and purges
    repositories older than DATA_RETENTION_HOURS.
    """
    while True:
        try:
            logger.info("Running snapshot & retention cleanup task...")
            async with get_worker_session() as db:
                now = datetime.now(timezone.utc)

                # 1. Clean up expired snapshots on disk
                res = await db.execute(
                    select(Repository).where(
                        Repository.snapshot_expires_at != None,
                        Repository.snapshot_expires_at < now,
                    )
                )
                expired_repos = res.scalars().all()
                for repo in expired_repos:
                    if repo.snapshot_path and os.path.exists(repo.snapshot_path):
                        try:
                            shutil.rmtree(repo.snapshot_path, ignore_errors=True)
                            logger.info("Removed expired snapshot dir for %s/%s", repo.owner, repo.name)
                        except Exception as e:
                            logger.warning("Failed to remove snapshot %s: %s", repo.snapshot_path, e)
                    repo.snapshot_path = None
                    repo.snapshot_expires_at = None

                # 2. Clean up repositories older than DATA_RETENTION_HOURS
                cutoff = now - timedelta(hours=settings.DATA_RETENTION_HOURS)
                old_res = await db.execute(
                    select(Repository).where(Repository.created_at < cutoff)
                )
                old_repos = old_res.scalars().all()
                for old_repo in old_repos:
                    if old_repo.snapshot_path and os.path.exists(old_repo.snapshot_path):
                        shutil.rmtree(old_repo.snapshot_path, ignore_errors=True)
                    await db.delete(old_repo)
                    logger.info("Purged aged repository %s/%s", old_repo.owner, old_repo.name)

                await db.commit()

        except Exception:
            logger.warning(
                "Snapshot and retention cleanup failed; it will retry on the next cycle."
            )

        # Sleep for 30 minutes
        await asyncio.sleep(1800)
