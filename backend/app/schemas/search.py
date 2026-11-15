from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SearchFilters(BaseModel):
    language: Optional[str] = None
    path_prefix: Optional[str] = None
    exclude_tests: bool = False


class SearchRequest(BaseModel):
    query: str = Field(..., max_length=500)
    mode: str = Field(default="hybrid", pattern="^(keyword|symbol|semantic|hybrid)$")
    limit: int = Field(default=20, ge=1, le=100)
    filters: Optional[SearchFilters] = None


class SearchResultItem(BaseModel):
    file_path: str
    start_line: int
    end_line: int
    snippet: str
    score: float
    source: List[str]  # e.g. ["keyword", "symbol", "semantic"]
    symbol_name: Optional[str] = None
    kind: Optional[str] = None


class SearchResponse(BaseModel):
    results: List[SearchResultItem]
    semantic_available: bool = True
