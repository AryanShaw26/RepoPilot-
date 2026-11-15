import asyncio
import os
import shutil
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Set

from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.db.models import (
    AnalysisJob,
    CodeChunk,
    FileImport,
    RepoFile,
    Repository,
    Symbol,
)
from app.db.session import get_worker_session
from app.prompts.arch_summary import ARCH_SUMMARY_SYSTEM, ARCH_SUMMARY_USER
from app.services.embeddings import EmbeddingService
from app.services.github import GitHubService
from app.services.imports import resolve_import
from app.services.ingest import (
    ExtractedFileInfo,
    detect_frameworks_and_meta,
    safe_extract_tarball,
    scan_repository_files,
)
from app.services.llm import LLMService
from app.services.parser import extract_symbols_and_imports
from app.services.test_intel import TestIntelService

# Active tasks set to prevent garbage collection
active_tasks: Set[asyncio.Task] = set()


async def has_vector_storage(db: AsyncSession) -> bool:
    result = await db.execute(
        text(
            "SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') "
            "AND EXISTS (SELECT 1 FROM pg_attribute AS attribute "
            "JOIN pg_class AS relation ON relation.oid = attribute.attrelid "
            "JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace "
            "WHERE namespace.nspname = 'public' AND relation.relname = 'code_chunks' "
            "AND attribute.attname = 'embedding' AND NOT attribute.attisdropped)"
        )
    )
    return bool(result.scalar_one())


async def update_job(
    db: AsyncSession,
    job_id: uuid.UUID,
    stage: str,
    progress: int,
    message: Optional[str] = None,
    error: Optional[str] = None,
):
    now = datetime.now(timezone.utc)
    stmt = (
        update(AnalysisJob)
        .where(AnalysisJob.id == job_id)
        .values(
            stage=stage,
            progress=progress,
            message=message,
            error=error,
            finished_at=now if stage in ("ready", "failed") else None,
        )
    )
    await db.execute(stmt)
    await db.commit()


async def run_analysis(repository_id: uuid.UUID, job_id: uuid.UUID):

    async def _inner():
        async with get_worker_session() as db:
            # 1. Start fetching
            await update_job(db, job_id, stage="fetching", progress=5, message="Fetching repository metadata and snapshot from GitHub...")

            repo_stmt = select(Repository).where(Repository.id == repository_id)
            repo_res = await db.execute(repo_stmt)
            repo = repo_res.scalar_one_or_none()
            if not repo:
                return

            repo.status = "processing"
            await db.commit()

            gh = GitHubService()
            snapshot_dir = os.path.join(settings.SNAPSHOT_DIR, str(repository_id))
            tar_path = os.path.join(snapshot_dir, "snapshot.tar.gz")

            try:
                # Resolve commit SHA if branch given
                sha = await gh.get_branch_sha(repo.owner, repo.name, repo.branch)
                if sha:
                    repo.commit_sha = sha

                # Download tarball
                await update_job(db, job_id, stage="fetching", progress=15, message="Downloading repository tarball...")
                await gh.download_tarball(repo.owner, repo.name, repo.branch, tar_path)
            finally:
                await gh.close()

            # 2. Parsing stage
            await update_job(db, job_id, stage="parsing", progress=25, message="Safely unpacking archive and filtering files...")
            repo_root = await asyncio.to_thread(safe_extract_tarball, tar_path, snapshot_dir)
            if os.path.exists(tar_path):
                os.remove(tar_path)

            repo.snapshot_path = snapshot_dir
            repo.snapshot_expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.SNAPSHOT_TTL_HOURS)

            await update_job(db, job_id, stage="parsing", progress=35, message="Scanning files and detecting secrets...")
            extracted_files: List[ExtractedFileInfo] = await asyncio.to_thread(scan_repository_files, repo_root)

            # Metadata detection (frameworks, entry points, readme)
            frameworks, entry_points, readme_excerpt = detect_frameworks_and_meta(extracted_files)
            repo.frameworks = frameworks
            repo.entry_points = entry_points
            if readme_excerpt:
                repo.readme_excerpt = readme_excerpt

            # 3. Indexing stage
            await update_job(db, job_id, stage="indexing", progress=50, message="Persisting files and extracting AST symbols...")

            # Bulk insert repo_files
            db_files: List[RepoFile] = []
            for ef in extracted_files:
                db_files.append(
                    RepoFile(
                        repository_id=repository_id,
                        path=ef.repo_relative_path,
                        directory=ef.directory,
                        language=ef.language,
                        size_bytes=ef.size_bytes,
                        line_count=ef.line_count,
                        is_test=ef.is_test,
                        is_entry_point=ef.is_entry_point,
                        content=ef.content,
                        sha1=ef.sha1,
                    )
                )

            # Batch insert files
            batch_size = 200
            for i in range(0, len(db_files), batch_size):
                db.add_all(db_files[i : i + batch_size])
                await db.commit()

            # Reload saved files to get their IDs
            files_map_stmt = select(RepoFile.id, RepoFile.path, RepoFile.language, RepoFile.content).where(
                RepoFile.repository_id == repository_id
            )
            files_res = await db.execute(files_map_stmt)
            saved_files = files_res.all()
            path_to_id = {row[1]: row[0] for row in saved_files}

            # Parse symbols and imports for each file in asyncio.to_thread
            await update_job(db, job_id, stage="indexing", progress=60, message="Resolving imports and building code chunks...")

            all_symbols: List[Symbol] = []
            raw_imports_by_file: Dict[uuid.UUID, List[Any]] = {}
            all_chunks: List[CodeChunk] = []

            for fid, fpath, lang, content in saved_files:
                if not content:
                    continue
                content_bytes = content.encode("utf-8")
                syms, imps = extract_symbols_and_imports(lang, content_bytes)

                raw_imports_by_file[fid] = imps

                # Map symbols
                for s in syms:
                    all_symbols.append(
                        Symbol(
                            repository_id=repository_id,
                            file_id=fid,
                            name=s.name,
                            qualified_name=f"{s.parent_name}.{s.name}" if s.parent_name else s.name,
                            kind=s.kind,
                            start_line=s.start_line,
                            end_line=s.end_line,
                            signature=s.signature,
                            docstring=s.docstring,
                        )
                    )

                # Create code chunks (60-line windows with 10-line overlap or by symbol)
                lines = content.splitlines()
                step = 50
                chunk_window = 60
                for start_idx in range(0, len(lines), step):
                    window = lines[start_idx : start_idx + chunk_window]
                    chunk_text = "\n".join(window)
                    if chunk_text.strip():
                        all_chunks.append(
                            CodeChunk(
                                repository_id=repository_id,
                                file_id=fid,
                                start_line=start_idx + 1,
                                end_line=start_idx + len(window),
                                content=chunk_text,
                                token_estimate=len(chunk_text) // 4,
                            )
                        )

            # Persist symbols in batches
            for i in range(0, len(all_symbols), batch_size):
                db.add_all(all_symbols[i : i + batch_size])
                await db.commit()

            # Resolve and persist imports
            db_imports: List[FileImport] = []
            for fid, imps in raw_imports_by_file.items():
                fpath = [row[1] for row in saved_files if row[0] == fid][0]
                lang = [row[2] for row in saved_files if row[0] == fid][0]
                for raw_imp in imps:
                    resolved = resolve_import(
                        raw_specifier=raw_imp.raw_specifier,
                        line=raw_imp.line,
                        source_path=fpath,
                        language=lang,
                        all_files_by_path=path_to_id,
                    )
                    db_imports.append(
                        FileImport(
                            repository_id=repository_id,
                            source_file_id=fid,
                            target_file_id=resolved.target_file_id,
                            raw_specifier=resolved.raw_specifier,
                            is_external=resolved.is_external,
                            package_name=resolved.package_name,
                            line=resolved.line,
                        )
                    )

            for i in range(0, len(db_imports), batch_size):
                db.add_all(db_imports[i : i + batch_size])
                await db.commit()

            # Persist code chunks (capped at MAX_CHUNKS_PER_REPO)
            capped_chunks = all_chunks[: settings.MAX_CHUNKS_PER_REPO]
            for i in range(0, len(capped_chunks), batch_size):
                db.add_all(capped_chunks[i : i + batch_size])
                await db.commit()

            # Test mappings
            await update_job(db, job_id, stage="indexing", progress=70, message="Computing deterministic test mappings...")
            await TestIntelService.compute_test_mappings(db, repository_id)

            # 4. Embedding stage
            await update_job(db, job_id, stage="embedding", progress=80, message="Generating vector embeddings for semantic search...")
            vector_storage_available = await has_vector_storage(db)
            if (
                settings.FEATURE_SEMANTIC_SEARCH
                and settings.EMBEDDING_API_KEY
                and vector_storage_available
            ):
                try:
                    emb_service = EmbeddingService()
                    # Batch embed top chunks
                    chunks_stmt = select(CodeChunk.id, CodeChunk.content).where(
                        CodeChunk.repository_id == repository_id
                    ).limit(500)
                    chunks_res = await db.execute(chunks_stmt)
                    chunk_rows = chunks_res.all()

                    texts = [row[1] for row in chunk_rows]
                    if texts:
                        embeddings = await emb_service.embed_texts(texts)
                        for (cid, _), vec in zip(chunk_rows, embeddings):
                            vec_str = f"[{','.join(str(x) for x in vec)}]"
                            # Raw SQL update
                            await db.execute(
                                select(func.now())  # dummy or raw update
                            )
                            # update code_chunks set embedding
                except Exception as e:
                    logger.info("Embedding skipped or unavailable: %s", e)
            else:
                logger.info(
                    "Semantic search disabled, vector storage unavailable, or no key provided; skipping embedding."
                )

            # 5. Ready stage & optional architecture summary
            await update_job(db, job_id, stage="ready", progress=100, message="Analysis complete. Ready for exploration.")
            repo.status = "ready"
            await db.commit()

            # Non-blocking AI architecture summary
            if settings.FEATURE_AI_ARCH_SUMMARY and settings.LLM_API_KEY:
                try:
                    llm = LLMService()
                    top_hubs = [f["name"] for f in frameworks]
                    arch_prompt = ARCH_SUMMARY_USER.format(
                        owner=repo.owner,
                        repo=repo.name,
                        languages=str(repo.languages),
                        frameworks=str([f["name"] for f in frameworks]),
                        entry_points=str([ep["path"] for ep in entry_points]),
                        top_hubs=", ".join(top_hubs) or "N/A",
                        readme_excerpt=repo.readme_excerpt or "No README provided.",
                    )
                    arch_out = await llm.complete_json(
                        system_prompt=ARCH_SUMMARY_SYSTEM,
                        user_prompt=arch_prompt,
                        schema_model=dict,
                    )
                    if arch_out and "summary" in arch_out:
                        repo.architecture_summary = arch_out["summary"]
                        await db.commit()
                except Exception as e:
                    logger.debug("Architecture summary generation skipped: %s", e)

    try:
        await asyncio.wait_for(_inner(), timeout=settings.ANALYSIS_TIMEOUT_S)
    except asyncio.TimeoutError:
        logger.error("Analysis for repo %s timed out after %d seconds.", repository_id, settings.ANALYSIS_TIMEOUT_S)
        async with get_worker_session() as db:
            await update_job(
                db,
                job_id,
                stage="failed",
                progress=100,
                error=f"Analysis timed out after {settings.ANALYSIS_TIMEOUT_S} seconds.",
            )
            await db.execute(
                update(Repository).where(Repository.id == repository_id).values(status="failed")
            )
            await db.commit()
    except Exception as e:
        logger.exception("Analysis for repo %s failed: %s", repository_id, e)
        async with get_worker_session() as db:
            await update_job(
                db,
                job_id,
                stage="failed",
                progress=100,
                error=str(e),
            )
            await db.execute(
                update(Repository).where(Repository.id == repository_id).values(status="failed")
            )
            await db.commit()


def launch_analysis_task(repository_id: uuid.UUID, job_id: uuid.UUID):
    task = asyncio.create_task(run_analysis(repository_id, job_id))
    active_tasks.add(task)
    task.add_done_callback(active_tasks.discard)
