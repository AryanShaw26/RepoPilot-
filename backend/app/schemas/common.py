from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Dict[str, Any] = {}


class ErrorResponse(BaseModel):
    error: ErrorDetail


class HealthResponse(BaseModel):
    status: str
    db: bool
    migrated: bool
    semantic_enabled: bool
    llm_configured: bool
    github_token_configured: bool
    version: str


class CapabilitiesResponse(BaseModel):
    semantic_search: bool
    llm_available: bool
    llm_unavailable_reason: Optional[str] = None
    llm_provider: str
    embedding_provider: str
    max_repo_size_mb: int
    max_files: int
    max_file_bytes: int
