import re
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import logger
from app.db.models import Investigation, InvestigationResult, RepoFile, Symbol
from app.prompts.investigate import INVESTIGATE_SYSTEM, INVESTIGATE_USER
from app.schemas.investigation import (
    EvidenceSnippet,
    Hypothesis,
    InvestigationResponse,
    IssueInfo,
    RankedResult,
    SymbolRef,
)
from app.schemas.search import SearchFilters, SearchResultItem
from app.services.llm import LLMService
from app.services.retrieval import RetrievalService, calculate_evidence_strength
from app.services.validator import CONSTANT_DISCLAIMER, validate_hypotheses


STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "can't", "cannot", "could",
    "couldn't", "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down",
    "during", "each", "few", "for", "from", "further", "had", "hadn't", "has",
    "hasn't", "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her",
    "here", "here's", "hers", "herself", "him", "himself", "his", "how", "how's",
    "i", "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it",
    "it's", "its", "itself", "let's", "me", "more", "most", "mustn't", "my",
    "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other",
    "ought", "our", "ours", "ourselves", "out", "over", "own", "same", "shan't",
    "she", "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such",
    "than", "that", "that's", "the", "their", "theirs", "them", "themselves", "then",
    "there", "there's", "these", "they", "they'd", "they'll", "they're", "they've",
    "this", "those", "through", "to", "too", "under", "until", "up", "very", "was",
    "wasn't", "we", "we'd", "we'll", "we're", "we've", "were", "weren't", "what",
    "what's", "when", "when's", "where", "where's", "which", "while", "who", "who's",
    "whom", "why", "why's", "with", "won't", "would", "wouldn't", "you", "you'd",
    "you'll", "you're", "you've", "your", "yours", "yourself", "yourselves", "error",
    "issue", "bug", "fix", "please", "help", "problem",
}


def extract_terms(text: str) -> Dict[str, List[str]]:
    """
    Deterministic extraction of:
    - identifiers (camelCase, snake_case, backticked tokens)
    - error strings (quoted strings, Exception/Error names)
    - file hints (words with / or file extensions)
    - keywords (filtered non-stopwords)
    """
    # Backticked tokens
    backticks = re.findall(r"`([^`]+)`", text)

    # Identifiers: camelCase, snake_case, or dotted
    identifiers = set(re.findall(r"\b[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)+\b", text))
    identifiers.update(re.findall(r"\b[a-z]+[A-Z][A-Za-z0-9]*\b", text))
    for bt in backticks:
        if len(bt) < 60 and not " " in bt:
            identifiers.add(bt)

    # Error strings
    error_strings = set(re.findall(r"\b[A-Z][A-Za-z0-9]*(?:Error|Exception|Failure|Fault)\b", text))
    quoted = re.findall(r"""['"]([^'"]{4,80})['"]""", text)
    for q in quoted:
        if any(term in q.lower() for term in ("error", "fail", "invalid", "cannot", "exception", "not found")):
            error_strings.add(q)

    # File hints
    file_hints = set(re.findall(r"\b[\w.-]+/[\w.-]+(?:\.[\w]+)?\b", text))
    file_hints.update(re.findall(r"\b[\w-]+\.(?:py|js|ts|tsx|jsx|go|java|json|yaml|yml|md)\b", text))

    # General keywords
    words = re.findall(r"\b[A-Za-z]{3,}\b", text.lower())
    keywords = [w for w in set(words) if w not in STOP_WORDS][:15]

    return {
        "identifiers": list(identifiers)[:10],
        "error_strings": list(error_strings)[:8],
        "file_hints": list(file_hints)[:8],
        "keywords": keywords,
    }


class LLMInvestigateOutput(BaseModel):
    why_relevant: Dict[str, str] = {}
    hypotheses: List[Dict[str, Any]] = []


class InvestigateService:
    @staticmethod
    async def run_investigation(
        db: AsyncSession,
        investigation_id: uuid.UUID,
        snapshot_dir: Optional[str] = None,
    ) -> None:
        # Load investigation
        stmt = (
            select(Investigation)
            .options(selectinload(Investigation.results))
            .where(Investigation.id == investigation_id)
        )
        res = await db.execute(stmt)
        inv = res.scalar_one_or_none()
        if not inv:
            return

        inv.status = "processing"
        await db.commit()

        try:
            full_text = f"{inv.issue_title or ''}\n{inv.issue_body}"
            terms = extract_terms(full_text)
            inv.extracted_terms = terms

            # Collect queries to run
            queries_to_run = []
            if terms["identifiers"]:
                queries_to_run.extend(terms["identifiers"][:3])
            if terms["error_strings"]:
                queries_to_run.extend(terms["error_strings"][:2])
            if terms["keywords"]:
                queries_to_run.append(" ".join(terms["keywords"][:4]))
            if not queries_to_run:
                queries_to_run = [full_text[:100]]

            all_search_results: List[SearchResultItem] = []
            seen_snippets: Set[str] = set()

            for q in queries_to_run:
                results, _ = await RetrievalService.hybrid_search(
                    db=db,
                    repository_id=inv.repository_id,
                    query=q,
                    snapshot_dir=snapshot_dir,
                    limit=10,
                    file_hints=terms["file_hints"],
                )
                for r in results:
                    key = f"{r.file_path}:{r.start_line}-{r.end_line}"
                    if key not in seen_snippets:
                        seen_snippets.add(key)
                        all_search_results.append(r)

            all_search_results.sort(key=lambda x: x.score, reverse=True)
            top_evidence = all_search_results[:12]

            # Calculate evidence strength
            exact_match = bool(terms["identifiers"] or terms["error_strings"])
            evidence_str = calculate_evidence_strength(top_evidence, exact_match_found=exact_match)
            inv.evidence_strength = evidence_str

            # Persist preliminary deterministic results
            # Map evidence items E1, E2, ...
            evidence_id_map: Dict[str, SearchResultItem] = {}
            db_results: List[InvestigationResult] = []

            # Preload files for file_id matching
            files_res = await db.execute(
                select(RepoFile.id, RepoFile.path).where(RepoFile.repository_id == inv.repository_id)
            )
            file_path_to_id = {path: fid for fid, path in files_res.all()}

            for rank, item in enumerate(top_evidence, 1):
                eid = f"E{rank}"
                evidence_id_map[eid] = item

                fid = file_path_to_id.get(item.file_path)
                db_results.append(
                    InvestigationResult(
                        investigation_id=inv.id,
                        rank=rank,
                        file_id=fid,
                        score=item.score,
                        retrieval_sources=item.source,
                        why_relevant="Identified via hybrid search matching extracted terms.",
                        evidence=[
                            {
                                "start_line": item.start_line,
                                "end_line": item.end_line,
                                "snippet": item.snippet,
                            }
                        ],
                    )
                )

            # Clear old and add new results
            inv.results = db_results
            await db.commit()

            # Now try LLM reasoning
            evidence_blocks = []
            for eid, item in evidence_id_map.items():
                evidence_blocks.append(
                    f"[{eid}] File: `{item.file_path}` (lines {item.start_line}-{item.end_line})\n"
                    f"```\n{item.snippet}\n```"
                )

            user_prompt = INVESTIGATE_USER.format(
                issue_title=inv.issue_title or "Untitled Issue",
                issue_body=inv.issue_body,
                evidence_blocks="\n\n".join(evidence_blocks) if evidence_blocks else "No evidence retrieved.",
            )

            try:
                llm = LLMService()
                llm_output: LLMInvestigateOutput = await llm.complete_json(
                    system_prompt=INVESTIGATE_SYSTEM,
                    user_prompt=user_prompt,
                    schema_model=LLMInvestigateOutput,
                )

                # Update why_relevant on results
                for r in inv.results:
                    eid = f"E{r.rank}"
                    if eid in llm_output.why_relevant:
                        r.why_relevant = llm_output.why_relevant[eid]

                # Validate hypotheses
                valid_eids = set(evidence_id_map.keys())
                validated_hypotheses = validate_hypotheses(llm_output.hypotheses, valid_eids)
                inv.hypotheses = [h.model_dump() for h in validated_hypotheses]

            except Exception:
                logger.warning("LLM reasoning unavailable; deterministic evidence was retained.")
                inv.error = "AI reasoning is unavailable; deterministic evidence was retained."
                # Hypotheses default to empty list, deterministic evidence preserved

            inv.status = "ready"
            await db.commit()

        except Exception as e:
            logger.error("Investigation processing failed (%s).", type(e).__name__)
            inv.status = "failed"
            inv.error = "Investigation processing failed."
            await db.commit()
