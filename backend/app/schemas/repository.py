import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class AnalyzeRepoRequest(BaseModel):
    url: str = Field(..., max_length=500, description="Public GitHub repository URL")
    branch: Optional[str] = Field(None, max_length=100, description="Optional branch or tag")


class AnalysisJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    repository_id: uuid.UUID
    stage: str
    progress: int
    message: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: datetime


class AnalyzeRepoResponse(BaseModel):
    repository_id: uuid.UUID
    job_id: uuid.UUID
    status: str


class RepositoryOverview(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner: str
    name: str
    url: str
    branch: str
    commit_sha: Optional[str] = None
    description: Optional[str] = None
    stars: Optional[int] = None
    license: Optional[str] = None
    topics: List[str] = []
    size_kb: Optional[int] = None
    languages: Dict[str, Any] = {}
    frameworks: List[Dict[str, Any]] = []
    entry_points: List[Dict[str, Any]] = []
    readme_excerpt: Optional[str] = None
    architecture_summary: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime
    stats: Optional[Dict[str, Any]] = None


class RepositorySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner: str
    name: str
    url: str
    branch: str
    commit_sha: Optional[str] = None
    description: Optional[str] = None
    stars: Optional[int] = None
    status: str
    created_at: datetime


class TreeNode(BaseModel):
    name: str
    path: str
    type: str  # "file" | "directory"
    size: Optional[int] = None
    language: Optional[str] = None
    is_test: Optional[bool] = None
    is_entry_point: Optional[bool] = None


class FileContentResponse(BaseModel):
    path: str
    directory: str
    language: Optional[str] = None
    size_bytes: int
    line_count: Optional[int] = None
    is_test: bool
    is_entry_point: bool
    content: Optional[str] = None


class SymbolItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    qualified_name: Optional[str] = None
    kind: str
    start_line: int
    end_line: int
    signature: Optional[str] = None
    docstring: Optional[str] = None
    file_path: Optional[str] = None


class ExplainSymbolResponse(BaseModel):
    explanation: str
    kind: str = "hypothesis"
    evidence: List[Dict[str, Any]] = []
    callers: List[Dict[str, Any]] = []
    imports: List[Dict[str, Any]] = []
    confidence: str = "medium"
