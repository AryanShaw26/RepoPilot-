from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class GraphNode(BaseModel):
    id: str
    label: str
    path: str
    language: Optional[str] = None
    in_degree: int = 0
    out_degree: int = 0
    type: str = "file"  # "file" | "folder" | "package"
    is_entry_point: bool = False
    in_cycle: bool = False
    file_count: Optional[int] = None


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    kind: str = "import"  # "import" | "contains"
    weight: int = 1


class GraphStats(BaseModel):
    total_nodes: int
    total_edges: int
    internal_imports: int
    external_imports: int
    cycles_detected: int
    note: Optional[str] = None


class GraphResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    stats: GraphStats
    cycles: List[List[str]] = []


class FileDependencyItem(BaseModel):
    specifier: str
    target_path: Optional[str] = None
    is_external: bool
    package_name: Optional[str] = None
    line: Optional[int] = None


class FileDependenciesResponse(BaseModel):
    path: str
    imports: List[FileDependencyItem]
    imported_by: List[FileDependencyItem]
