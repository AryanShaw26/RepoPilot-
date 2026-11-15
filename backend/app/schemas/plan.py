import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CreatePlanRequest(BaseModel):
    user_notes: Optional[str] = Field(None, max_length=5000)


class PlanStep(BaseModel):
    order: int
    title: str
    description: str
    files: List[str] = []
    kind: str = "hypothesis"  # "fact" | "hypothesis"


class ImpactedFile(BaseModel):
    path: str
    reason: str
    kind: str = "fact"


class RiskItem(BaseModel):
    text: str
    kind: str = "hypothesis"
    confidence: str = "low"  # "low" | "medium" | "high"


class ExistingTest(BaseModel):
    path: str
    method: str
    confidence: str
    kind: str = "fact"


class RecommendedTest(BaseModel):
    scenario: str
    kind: str = "hypothesis"


class TestRecommendations(BaseModel):
    existing: List[ExistingTest] = []
    recommended: List[RecommendedTest] = []


class PlanContent(BaseModel):
    summary: Dict[str, Any]  # {"text": "...", "kind": "hypothesis"}
    steps: List[PlanStep]
    impacted_files: List[ImpactedFile]
    risks: List[RiskItem]
    validation_checklist: List[str]
    tests: TestRecommendations
    disclaimer: str


class PlanResponse(BaseModel):
    id: uuid.UUID
    investigation_id: uuid.UUID
    user_notes: Optional[str] = None
    plan: PlanContent
    markdown: Optional[str] = None
    created_at: datetime
    disclaimer: str


class TestIntelOverview(BaseModel):
    test_files_count: int
    source_files_count: int
    mapped_source_files_count: int
    coverage_proxy_pct: float
    detected_frameworks: List[str]
    sample_mappings: List[Dict[str, Any]] = []
    disclaimer: str = "RepoPilot finds and suggests tests. It does not run them."
