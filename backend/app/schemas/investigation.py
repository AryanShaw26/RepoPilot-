import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CreateInvestigationRequest(BaseModel):
    source_type: str = Field(..., pattern="^(text|github_issue)$")
    issue_title: Optional[str] = Field(None, max_length=500)
    issue_body: Optional[str] = Field(None, max_length=20000)
    issue_url: Optional[str] = Field(None, max_length=500)


class EvidenceSnippet(BaseModel):
    start_line: int
    end_line: int
    snippet: str


class SymbolRef(BaseModel):
    name: str
    kind: str
    start_line: int
    end_line: int


class RankedResult(BaseModel):
    rank: int
    file_path: str
    symbol: Optional[SymbolRef] = None
    score: float
    retrieval_sources: List[str]
    why_relevant: Dict[str, Any]  # {"text": "...", "kind": "hypothesis"}
    evidence: List[EvidenceSnippet]


class Hypothesis(BaseModel):
    id: str
    text: str
    kind: str = "hypothesis"
    confidence: str  # "low" | "medium" | "high"
    evidence_refs: List[str] = []
    unsupported: bool = False


class IssueInfo(BaseModel):
    title: Optional[str] = None
    body: str
    url: Optional[str] = None


class InvestigationResponse(BaseModel):
    id: uuid.UUID
    status: str
    issue: IssueInfo
    extracted_terms: Dict[str, Any] = {}
    evidence_strength: str = "moderate"  # "weak" | "moderate" | "strong"
    results: List[RankedResult] = []
    hypotheses: List[Hypothesis] = []
    disclaimer: str
    error: Optional[str] = None
    created_at: datetime
