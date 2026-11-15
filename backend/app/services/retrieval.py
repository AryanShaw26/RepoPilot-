import os
import posixpath
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.db.models import CodeChunk, RepoFile
from app.schemas.search import SearchFilters, SearchResultItem
from app.services.embeddings import EmbeddingService, FeatureDisabled
from app.services.search import (
    search_database_keyword,
    search_ripgrep,
    search_symbols,
)


def rrf_fusion(
    rank_lists: Dict[str, List[SearchResultItem]],
    k: int = 60,
) -> List[SearchResultItem]:
    """
    Reciprocal Rank Fusion (RRF, k=60) combining keyword, symbol, and semantic search.
    Merges results by (file_path, start_line, end_line) or (file_path, symbol_name).
    """
    scores: Dict[Tuple[str, int, int], float] = defaultdict(float)
    sources: Dict[Tuple[str, int, int], Set[str]] = defaultdict(set)
    items_map: Dict[Tuple[str, int, int], SearchResultItem] = {}

    for source_name, items in rank_lists.items():
        for rank, item in enumerate(items, 1):
            key = (item.file_path, item.start_line, item.end_line)
            scores[key] += 1.0 / (k + rank)
            sources[key].add(source_name)
            if key not in items_map:
                items_map[key] = item

    sorted_keys = sorted(scores.keys(), key=lambda k_item: scores[k_item], reverse=True)

    fused_results: List[SearchResultItem] = []
    for key in sorted_keys:
        item = items_map[key]
        item.score = round(scores[key], 4)
        item.source = sorted(list(sources[key]))
        fused_results.append(item)

    return fused_results


def calculate_evidence_strength(
    results: List[SearchResultItem],
    exact_match_found: bool = False,
) -> str:
    """
    Evaluates evidence strength:
    - strong: >= 3 results from >= 2 sources including an exact match
    - moderate: results from >= 2 sources or one exact match
    - weak: otherwise
    """
    if not results:
        return "weak"

    multi_source_count = sum(1 for r in results if len(r.source) >= 2)
    has_multiple_sources = any(len(r.source) >= 2 for r in results)

    if multi_source_count >= 3 and exact_match_found:
        return "strong"
    if has_multiple_sources or exact_match_found or len(results) >= 5:
        return "moderate"
    return "weak"


class RetrievalService:
    @staticmethod
    async def semantic_storage_available(db: AsyncSession) -> bool:
        if not settings.FEATURE_SEMANTIC_SEARCH or not settings.EMBEDDING_API_KEY:
            return False

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

    @staticmethod
    async def hybrid_search(
        db: AsyncSession,
        repository_id: uuid.UUID,
        query: str,
        snapshot_dir: Optional[str] = None,
        limit: int = 20,
        filters: Optional[SearchFilters] = None,
        file_hints: Optional[List[str]] = None,
    ) -> Tuple[List[SearchResultItem], bool]:
        """
        Executes hybrid search combining:
        1. Keyword search (ripgrep / DB fallback)
        2. Symbol search
        3. Semantic search (pgvector if available)
        Fuses with RRF.
        Returns (fused_results, semantic_available).
        """
        rank_lists: Dict[str, List[SearchResultItem]] = {}
        semantic_available = await RetrievalService.semantic_storage_available(db)

        # 1. Keyword search
        kw_results: List[SearchResultItem] = []
        if snapshot_dir and os.path.exists(snapshot_dir):
            kw_results = await search_ripgrep(snapshot_dir, query, limit=limit, filters=filters)

        if not kw_results:
            kw_results = await search_database_keyword(
                db, repository_id, query, limit=limit, filters=filters
            )
        rank_lists["keyword"] = kw_results

        # 2. Symbol search
        sym_results = await search_symbols(db, repository_id, query, limit=limit)
        rank_lists["symbol"] = sym_results

        # 3. Semantic search
        if semantic_available:
            try:
                emb_service = EmbeddingService()
                q_vec = await emb_service.embed_query(query)
                if q_vec:
                    # Query pgvector code_chunks table via raw SQL
                    vec_str = f"[{','.join(str(x) for x in q_vec)}]"
                    sql = text(
                        """
                        SELECT c.id, f.path, c.start_line, c.end_line, c.content,
                               1 - (c.embedding <=> :qvec::vector) AS similarity
                        FROM code_chunks c
                        JOIN repo_files f ON c.file_id = f.id
                        WHERE c.repository_id = :repo_id
                          AND c.embedding IS NOT NULL
                        ORDER BY c.embedding <=> :qvec::vector
                        LIMIT :limit
                        """
                    )
                    res = await db.execute(sql, {"repo_id": repository_id, "qvec": vec_str, "limit": limit})
                    sem_items = []
                    for row in res.fetchall():
                        sem_items.append(
                            SearchResultItem(
                                file_path=row[1],
                                start_line=row[2],
                                end_line=row[3],
                                snippet=row[4][:300],
                                score=float(row[5]) if row[5] else 0.5,
                                source=["semantic"],
                            )
                        )
                    rank_lists["semantic"] = sem_items
            except Exception:
                logger.debug("Semantic search failed; continuing with deterministic results.")
                semantic_available = False

        # Fuse
        fused = rrf_fusion(rank_lists, k=60)

        # Apply file hints boost and test downweights
        query_mentions_tests = bool(re.search(r"\b(?:tests?|spec|testing)\b", query, re.IGNORECASE))

        for item in fused:
            # File hint boost
            if file_hints:
                for hint in file_hints:
                    if hint.lower() in item.file_path.lower():
                        item.score *= 1.3
                        break

            # Downweight tests if query doesn't mention tests
            if not query_mentions_tests:
                if "test" in item.file_path.lower() or "spec" in item.file_path.lower():
                    item.score *= 0.7

        fused.sort(key=lambda x: x.score, reverse=True)
        return fused[:limit], semantic_available
